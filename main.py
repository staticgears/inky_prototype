import inky_frame

BUTTON_A = 1
BUTTON_B = 2
BUTTON_C = 4
BUTTON_D = 8
BUTTON_E = 16

# Check which button is still held down right at boot because evidently if you delay this information can be lost
g_bttn_event = 0
if inky_frame.woken_by_button():
    # Check which button is still held down right at boot
    g_bttn_event = (
        (BUTTON_A * inky_frame.button_a.raw())
        | (BUTTON_B * inky_frame.button_b.raw())
        | (BUTTON_C * inky_frame.button_c.raw())
        | (BUTTON_D * inky_frame.button_d.raw())
        | (BUTTON_E * inky_frame.button_e.raw())
    )

import gc, json, network, os, random, time
import jpegdec
from machine import RTC

# Default to on just incase we haven't read the config yet
DEBUG=1

def log_debug(ctxt, msg):
    global DEBUG
    if DEBUG:
        _, _, _, _, hours, minutes, seconds, _ = RTC().datetime()
        print(f"DEBUG :: [{hours}:{minutes}:{seconds}] {ctxt} -> {msg}")

on_pc = False
try:
    # MicroPython
    import urequests
except ImportError:
    import requests as urequests
    on_pc = True
    print("DEBUG ::::::  Running on standard Python")

#######################
# File System Helpers #
#######################
def _mount_sd():
    # Limit scope of imports for memory health
    import sdcard
    from machine import SPI, Pin
    mount_point = "/" + SD_MOUNT
    # Clean up any existing mount point from a previous soft-reset
    try:
        os.umount(mount_point)
    except OSError:
        # Ignore error if it wasn't mounted in the first place
        pass

    Pin(17, machine.Pin.OUT, value=1)
    cs = Pin(22, Pin.OUT, value=1)

    sd_spi = None
    try:
        # set up the SD card
        sd_spi = SPI(0, baudrate=100_000, sck=Pin(18, Pin.OUT), mosi=Pin(19, Pin.OUT), miso=Pin(16, Pin.OUT))


        # Flush the card: Send 80+ clock cycles with CS HIGH
        # This clears any hung state from an interrupted read/write
        cs.value(1)
        sd_spi.write(b'\xff' * 10)
        time.sleep_ms(10)

        sd = sdcard.SDCard(sd_spi, cs)
        os.mount(sd, mount_point)
        log_debug("_mount_sd", "SD card mounted successfully.")
        return True
    except OSError as e:
        log_debug("_mount_sd", f"Caught OSError: {e}")
        if sd_spi:
            sd_spi.deinit()  # Release SPI hardware before retrying
            sd_spi = None
            time.sleep_ms(250)
        return False

def mount_sd(retries=5):
    if not on_pc:
        success = False
        for attempt in range(1, retries + 1):
            if _mount_sd():
                success = True
                break
            log_debug("mount_sd", "reattempting SD card mount after failure...")
        if not success:
            raise RuntimeError(f"Failed to mount SD card after {retries} attempts.")

def file_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

def path_join(p1, p2):
    return p1 + "/" + p2

def makedirs(path):
    parts = path.split("/")
    current = ""
    for part in parts:
        if not part:
            continue
        current = current + "/" + part if path.startswith("/") else (current + "/" + part if current else part)
        try:
            os.mkdir(current)
        except OSError as e:
            # 17 is EEXIST (directory already exists)
            if e.args[0] != 17:
                raise

#################
# Config Parser #
#################
def parse_config(filepath: str) -> dict[str, str]:
    """Reads a 'variable=value' text file and returns a dictionary."""
    config = {}

    with open(filepath, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            # Skip empty lines and comment lines starting with '#'
            if not line or line.startswith("#"):
                continue

            # Split only on the first '=' in case the value contains '='
            if "=" in line:
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()

    return config

###########################
# Graphics initialization #
###########################
g_graphics = None
def graphics_init():
    global g_graphics
    if not on_pc:
        # Limit scope of imports for memory health
        # from picographics import DISPLAY_INKY_FRAME_4 as DISPLAY  # 4.0"
        # from picographics import DISPLAY_INKY_FRAME as DISPLAY    # 5.7"
        # from picographics import DISPLAY_INKY_FRAME_7 as DISPLAY  # 7.3"
        from picographics import DISPLAY_INKY_FRAME_SPECTRA_7 as DISPLAY  # 7.3" Spectra
        from picographics import PicoGraphics

        # Initialise the Display
        g_graphics = PicoGraphics(DISPLAY)

#############
# Constants #
#############
SD_MOUNT = 'sd' 
graphics_init()
mount_sd()

cfg_path =  path_join(SD_MOUNT, 'config.ini')
config = parse_config(cfg_path)
DEBUG = int(config['debug'])
WIFI_SSID = config['wifi_ssid']
WIFI_PASSWORD = config['wifi_password'] 
JSON_MAP_URL = config['json_map_url'] 
CHUNK_SIZE=int(config['chunk_size'])
IMAGES_DIR = path_join(SD_MOUNT, config['images_dir'])
PERIOD_IN_MINUTES = int(config['time_period_in_minutes'])
PERIOD_IN_MINUTES = 1
HOUR_LOWER_BOUND=int(config['time_hour_lower_bound'])
HOUR_UPPER_BOUND=int(config['time_hour_upper_bound'])
TZ_OFFSET=int(config.get('time_tz_offset', '-8'))
LED_BUTTONS = [inky_frame.button_a, inky_frame.button_b, inky_frame.button_c, inky_frame.button_d, inky_frame.button_e]
LED_BUSY = inky_frame.led_busy 
LED_WIFI = inky_frame.led_wifi
config = None # Release memory

##################
# Initialisation #
##################
# global image index skip, for button based fast forwarding and randomization
g_idx_offset = 0

def wifi_connect(disconnect):
    if not network.WLAN:
        print("Skipping WIFI code on PC")
        return

    # Connect to WiFi
    gc.collect()
    if disconnect:
        try:
            wlan.disconnect()
            time.sleep(0.5)
        except Exception as e:
            log_warning(f"Failure to disconnect from wifi, Reason: {e}")
        finally:
            wlan.active(False)

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # Connect to your network
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    connection_timeout = 10
    while connection_timeout > 0:
        if wlan.status() >= 3:
            break
        connection_timeout -= 1
        log_debug('wifi_connect', 'Waiting for Wi-Fi connection...')
        time.sleep(1)
    if wlan.status() != 3:
        wlan.active(False)
        raise RuntimeError('Failed to establish a network connection')
    else:
        log_debug('wifi_connect', 'Connection successful!')
        inky_frame.set_time()
        log_debug("main", "Logging after ntp time sync.")

def hardware_init():
    makedirs(IMAGES_DIR)

    # Connect to WiFi
    wifi_connect(disconnect=False)

    # Sync time
    inky_frame.pcf_to_pico_rtc()
 
###########
# Logging #
###########
def log_warning(msg):
    """ Abstract warning logging incase we get fancier with LED incators, email, or unified logger """
    print(msg)
    write_text(msg, error=False)

def log_error(msg):
    """ Abstract error logging incase we get fancier with LED incators, email, or unified logger """
    print(msg)
    write_text(msg, error=True)

#############################
# File / Network Operations #
#############################
def _get_image_path(filename):
    return path_join(IMAGES_DIR, filename)

def check_existence_of_image(filename):
    path = _get_image_path(filename)
    return file_exists(path)
    
def list_images():
    return os.listdir(IMAGES_DIR)

def _get_most_recent_image_filename():
    """
       Return the filename of the most recently modified image or None if the IMAGES_DIR is empty.
       Note: if multiple were downloaded in the same chunk the order is indeterminate.
    """
    latest_filename = None
    latest_mtime = -1

    for entry in os.ilistdir(IMAGES_DIR):
        filename = entry[0]
        type = entry[1]

        # 0x8000 is the standard MicroPython bitmask for a regular file (ignores folders)
        if type == 0x8000:
            path = _get_image_path(filename)
            # Index 8 in os.stat() is st_mtime (modification time)
            mtime = os.stat(path)[8]

            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_filename = filename

    return latest_filename

def delete_image(filename):
    #TODO does deleting a displayed image require special handling, for now I'm assuming not
    try:
        path = _get_image_path(filename)
        if file_exists(path):
            os.remove(path)
    except Exception as e:
        log_error(f"Failed to delete {file_path}. Reason: {e}")

def delete_sd_files_with_filter(names_filter_set):
    """ Delete all files in the IMAGES_DIR, except those found in the names_filter_set """
    if not file_exists(IMAGES_DIR):
        return
    for filename in list_images():
        if filename not in names_filter_set:
            delete_image(filename) 

def write_text(msg, error, update=True):
    global g_graphics
    if g_graphics:
      WIDTH, HEIGHT = g_graphics.get_bounds()
      g_graphics.set_font("bitmap8")
      g_graphics.set_pen(inky_frame.WHITE)
      g_graphics.clear()
      g_graphics.set_pen(inky_frame.RED if error else inky_frame.YELLOW)
      # g_graphics.measure_text(text, scale, spacing, fixed_width)
      g_graphics.text(msg, 10, 10, WIDTH-30, scale=3)
      if update:
          g_graphics.update()
      

def _display_jpeg(filename):
    global g_graphics
    if not g_graphics:
        return
    path = _get_image_path(filename)
    log_debug("_display_jpeg", f"loading image at path = {path} ...")
    if not file_exists(path):
        log_warning(f"Now image found, may resolve itself in a few minutes, {path}...")
        return
    
    try:
        gc.collect()
        screen_w, screen_h = g_graphics.get_bounds()
        # Choose a colour and uncomment these lines to choose a background colour
        # Colour options: BLACK, WHITE, GREEN, BLUE, RED, YELLOW, ORANGE, TAUPE
        g_graphics.set_pen(inky_frame.BLACK)
        g_graphics.clear()

        # TODO in the example this was a singleton, but that seems unncessary
        j = jpegdec.JPEG(g_graphics)
        j.open_file(path)
        screen_w, screen_h = g_graphics.get_bounds()
        x_offset = max(0, (screen_w - j.get_width()) // 2)
        y_offset = max(0, (screen_h - j.get_height()) // 2)
        j.decode(x_offset, y_offset, jpegdec.JPEG_SCALE_FULL)
        g_graphics.update()
        log_debug("_display_jpeg", "Successfully loaded image.")
    except Exception as e:
        log_error(f"CRITICAL :: An error occurred displaying image: {e}")
        delete_image(filename)

def display_image_by_recency():
    """
       Unlike display_image_by_time_rotation, this method attempt to find the most recently downloaded image and display it.
       This lasts until the next time window's rotation at which time things will revert to display_image_by_time_rotation.
       This is intended as a manual overrride to kind of say, look what I sent you.
    """
    filename = _get_most_recent_image_filename()
    if filename:
        log_debug("display_image_by_recency", f"filename = {filename}")
        _display_jpeg(filename)
    else:
       log_warning("No images to display inside of display_image_by_recency")
       return

def tz_adjust(month, day, hour, tz_offset):
    dst_adjusted_offset = tz_offset
    dst_months = {3, 4, 5, 6, 7, 8, 9, 10, 11}
    if month in dst_months and not ((month == 3 and day < 14) or (month == 11 and day >= 7)):
        dst_adjusted_offset += 1
    return (hour + dst_adjusted_offset + 24) % 24

def display_image_by_time_rotation():
    """
       The goal is to rotate an image based on teh hour, but avoid certain images only displaying during night time.
       HOUR_LOWER_BOUND + HOUR_UPPER_BOUND configure the waking hours 0 -23 inclusive
       In combinatio nwith an number of hours since the begining of the month, we module against hte number of aivlable images
    """
    global g_idx_offset
    monthly_minute_epoc = 0
    year, month, day, _, hours, minutes, _, _ = RTC().datetime()
    if year < 2023:
       inky_frame.set_time()  # Sets both the Inky and Pico RTC
       year, month, day,_, hours, minutes, _, _ = RTC().datetime()

    hours = tz_adjust(month, day, hours, TZ_OFFSET)

    if hours < HOUR_LOWER_BOUND:
       monthly_minute_epoc = 0
    elif hours > HOUR_UPPER_BOUND:
       monthly_minute_epoc = HOUR_UPPER_BOUND*60
    else:
       monthly_minute_epoc = hours*60 + minutes

    monthly_minute_epoc += (day - 1)*24*60
    sorted_paths = sorted(list_images())
    if len(sorted_paths) == 0:
       log_warning("No images to display inside of display_image_by_time_rotation")
       return
    idx = ((monthly_minute_epoc // PERIOD_IN_MINUTES) + g_idx_offset) % len(sorted_paths)
    filename = sorted_paths[idx]
    log_debug("display_image_by_time_rotation", f"filename = {filename}, idx={idx}, g_idx_offset={g_idx_offset}")
    _display_jpeg(filename)

def _resolve_redirect_url(base_url, location):
    """Resolves relative redirect Location headers against the current URL."""
    if location.startswith("http://") or location.startswith("https://"):
        return location

    # Extract scheme and host (e.g., "https://example.com")
    scheme_end = base_url.find("://") + 3
    path_start = base_url.find("/", scheme_end)
    origin = base_url if path_start == -1 else base_url[:path_start]

    if location.startswith("/"):
        return origin + location

    # Handle relative path without leading slash
    last_slash = base_url.rfind("/")
    if last_slash >= scheme_end:
        return base_url[: last_slash + 1] + location
    return origin + "/" + location

def _download_urequest(url, path, max_redirects=5):
    """
        Complex overloading because this supports two usecases in order to reuse the 30X handling code
        @returns (body, status)
          - status -> a boolean success vs failure
          if path = None then body will contkain the response body ie the content
          if path is not None then body = "" aka empty string
          Note if status == False then body always = ""
    """
    current_url = url
    redirects = 0

    while redirects <= max_redirects:
        response = None
        try:
            gc.collect()
            response = urequests.get(current_url)
            status_code = response.status_code

            # Handle 30X redirects
            if status_code in (301, 302, 303, 307, 308):
                location = None
                if hasattr(response, "headers") and response.headers:
                    for k, v in response.headers.items():
                        if k.lower() == "location":
                            location = v
                            break

                response.close()
                response = None

                if not location:
                    log_error(f"Redirect status {status_code} received but no Location header found.")
                    return ("", False)

                current_url = _resolve_redirect_url(current_url, location)
                log_debug("_download_urequest", f"Received a redirect to {current_url}")
                redirects += 1
                continue # Loop back to request the new URL

            if status_code != 200:
                log_error(f"HTTP ErrorL {status_code} while attempting google drive download.")
                response.close()
                return ("", False)

            # Usecase 1: Return response content in memory
            if path is None:
                body = response.content.decode("utf-8")
                response.close()
                gc.collect()
                log_debug("_download_urequest", f"Success, contents read into memory:\n{body}\n--------END BODY--------")
                return (body, True)
            else:
                # Usecase 2: Stream response directly to file in chunks to save RAM
                with open(path, "wb") as f:
                    while True:
                        chunk = response.raw.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                        # Proactively call garbage collection during heavy I/O
                        gc.collect()

                log_debug("_download_urequest", f"Success, File written {path}")
                response.close()
                gc.collect()
                return ("", True)

        except Exception as e:
            log_error(f"Download from Google Drive failed: {e}")
            return ("", False)
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception as e:
                    pass
            gc.collect()
    # Exceeded max_redirects
    log_error("Too many redirects while attempting google drive download")
    gc.collect()
    return ("", False)

def download_image(filename, url):
    path = _get_image_path(filename)
    if file_exists(path):
       return False
    log_debug("download_image", f"attempting to download: {url}")
    (_, result) = _download_urequest(url, path)
    if not result:
      #Attempt to cleanup incase of mid download problems, not 100% robust, but should be pretty stable
      delete_image(filename)
    log_debug("download_image", "Success")
    return result

############
# JSON Map #  
############
def load_json_body(url):
    """
       Load a json file that indicates which images need to be deleted / downloaded
       Format is a json list with this structure, all fields are required.
       url  - STRING public url to download the file, following redirects will be required
       [ { "name": "beach_2025.jpg" , "url": "https://drive.google.com/uc?export=view&id={file_id}" ] 
    """
    (payload, result) = _download_urequest(url, None)
    if payload and result:
        return json.loads(payload)
    else:
        return None

def process_json_body(json_body):
   """ 
       See load_json_body for json structure and semantics 
       !. Delete files on SD card not listed in the map
       2. Skip files that already exist in the IMAGES_DIR location
       3. Download new files and save them to the IMAGES_DIR location
   """

   if not json_body:
       return

   active_name_set = {item['name'] for item in json_body if 'name' in item}
   # Step 1: Delete files on SD card not listed in the map
   delete_sd_files_with_filter(active_name_set)

   for img_entry in json_body:
       name = img_entry['name']

       # Step 2: Skip existing files
       if check_existence_of_image(name):
           continue

       # Step 3: Download new files
       log_debug("process_json_body", f"Downloading image {name} from {img_entry['url']}")
       download_image(name, img_entry['url'])

################
# LED controls #
################
def reset_all_leds():
    for btn in LED_BUTTONS:
        btn.led_off()

def blink_led(btn, delay_in_seconds=0.3, times=1):
    """
        Aassumes led is in the off position, failing this it jsut stays one for delay_in_seconds and then goes off.
        LED is always left in the off state afterwards.
        Execution takes 2 X delay_in_seconds X times
    """
    btn.led_on()
    for _ in range(times-1):
        time.sleep(delay_in_seconds)
        btn.led_toggle()
        time.sleep(delay_in_seconds)
        btn.led_toggle()
    time.sleep(delay_in_seconds)
    btn.led_toggle()
    
    
def cycle_all_leds(delay_in_seconds=0.3, blink=True):
    """ Cycle through each button, this takes 5x delay_in_seconds + 10x _blink_delay_in_seconds if blink is enabled """
    for btn in LED_BUTTONS:
        blink_led(btn, delay_in_seconds, times=1)

#############
# Main Loop #
#############
def main_loop():
    global g_idx_offset, g_bttn_event
    hardware_init()
    reset_all_leds()
    cycle_all_leds()
    blink_cnt=3
    while True:
        # On each loop reset these to prevent getting stuck on teh most recent
        refresh_json_map = True
        use_display_by_time_rotation=True
        img_cnt = len(list_images())

        # Step 1: Handle Button Events
        if g_bttn_event & BUTTON_A:
            # Increment to the next picture
            log_debug("main", "button A was pressed.")
            blink_led(inky_frame.button_a, times=blink_cnt)
            g_idx_offset += 1
            refresh_json_map = (img_cnt == 0) # Only refresh if we have no images
        elif g_bttn_event & BUTTON_B:
            # Increment a random next picture
            log_debug("main", "button B was pressed.")
            blink_led(inky_frame.button_b, times=blink_cnt)
            max_img_idx = max(img_cnt - 1, 0)
            g_idx_offset += random.randint(0, max_img_idx)
            #g_idx_offset += random.randrange(img_cnt)
            refresh_json_map = (img_cnt == 0) # Only refresh if we have no images
        elif g_bttn_event & BUTTON_C:
            log_debug("main", "button C was pressed.")
            blink_led(inky_frame.button_c, times=blink_cnt)
            use_display_by_time_rotation=False
            refresh_json_map = (img_cnt == 0) # Only refresh if we have no images
        elif g_bttn_event & BUTTON_D:
            # Wakes up device from sleep and force a json_map_refresh
            log_debug("main", "button D was pressed.")
            blink_led(inky_frame.button_d, times=blink_cnt)
            refresh_json_map = True
        elif g_bttn_event & BUTTON_E:
            # Reset - delete images directory and attempt to redownload
            log_debug("main", "button E was pressed.")
            blink_led(inky_frame.button_e, times=blink_cnt)
            g_idx_offset = 0
            delete_sd_files_with_filter(set())
            refresh_json_map = True

        # Step 2: Cleanup old images and add new ones
        if refresh_json_map:
            json_body = load_json_body(JSON_MAP_URL)
            if json_body:
                process_json_body(json_body)
            else:
                log_warning("Unable to download new pictures due to failure of load_json_body")

        # Step 3: Select which image to display
        if use_display_by_time_rotation:
            display_image_by_time_rotation()
        else:
            display_image_by_recency()

        # Step 4: Go to sleep
        log_debug("main", "Going to sleep now.")
        inky_frame.sleep_for(PERIOD_IN_MINUTES)

if __name__ == "__main__":
    """ See testbench.py for manual testing off the device. """
    main_loop()
