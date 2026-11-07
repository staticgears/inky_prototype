import configparser, gc, json, os, random, time
import inky_frame
import jpegdec
from machine import RTC

if 'g_inky_stubs' not in globals():
    from urllib import request as urequest
else:
    from urllib import urequest

def mount_sd():
    # Limit scope of imports for memory health
    from machine import SPI, Pin
    if SPI:
        import sdcard
        # set up the SD card
        sd_spi = SPI(0, sck=Pin(18, Pin.OUT), mosi=Pin(19, Pin.OUT), miso=Pin(16, Pin.OUT))
        sd = sdcard.SDCard(sd_spi, Pin(22))
        os.mount(sd, "/" + SD_MOUNT)
    
#############
# Constants #
#############
SD_MOUNT = 'sd' 
mount_sd()
cfg_path =  os.path.join(SD_MOUNT, 'config.ini')
config = configparser.ConfigParser()
config.read(cfg_path)
WIFI_SSID = config['wifi']['ssid']
WIFI_PASSWORD = config['wifi']['password'] 
JSON_MAP_URL = config['misc']['json_map_url'] 
CHUNK_SIZE=config.getint('misc', 'chunk_size')
IMAGES_DIR = os.path.join(SD_MOUNT, config['misc']['images_dir'])
PERIOD_IN_MINUTES = config.getint('time', 'period_in_minutes')
HOUR_LOWER_BOUND=config.getint('time', 'hour_lower_bound')
HOUR_UPPER_BOUND=config.getint('time', 'hour_upper_bound')
TIMEZONE=config['time']['tz']
LED_BUTTONS = [inky_frame.button_a, inky_frame.button_b, inky_frame.button_c, inky_frame.button_d, inky_frame.button_e]
LED_BUSY = inky_frame.led_busy 
LED_WIFI = inky_frame.led_wifi
config = None # Release memory

##################
# Initialisation #
##################
g_graphics = None 
# global image index skip, for button based fast forwarding and randomization
g_idx_offset = 0

def wifi_connect(disconnect):
    # Limit scope of imports for memory health
    import inky_helper

    # Connect to WiFi
    gc.collect()
    if disconnect:
        try:
            inky_helper.network_disconnect()
        except ImportError:
            log_warning("Failure to disconnect from wifi")

    try:
        inky_helper.network_connect(WIFI_SSID, WIFI_PASSWORD)
    except ImportError:
        log_error("Failure to connect to wifi")

def hardware_init():
    os.makedirs(IMAGES_DIR, exist_ok=True)

    # Limit scope of imports for memory health
    # from picographics import DISPLAY_INKY_FRAME_4 as DISPLAY  # 4.0"
    # from picographics import DISPLAY_INKY_FRAME as DISPLAY    # 5.7"
    # from picographics import DISPLAY_INKY_FRAME_7 as DISPLAY  # 7.3"
    from picographics import DISPLAY_INKY_FRAME_SPECTRA_7 as DISPLAY  # 7.3" Spectra
    from picographics import PicoGraphics

    # Sync time
    inky_frame.pcf_to_pico_rtc() 

    # Initialise the Display
    g_graphics = PicoGraphics(DISPLAY)

    # TODO This part may not be needed, seen in https://github.com/pimoroni/inky-frame/blob/main/examples/inky_frame_news.py
    # intialise the pcf85063a real time clock chip
    from pimoroni_i2c import PimoroniI2C
    from pcf85063a import PCF85063A
    I2C_SDA_PIN = 4
    I2C_SCL_PIN = 5
    i2c = PimoroniI2C(I2C_SDA_PIN, I2C_SCL_PIN, 100000)
    rtc = PCF85063A(i2c)
    rtc.enable_timer_interrupt(True)

    # Connect to WiFi
    wifi_connect(disconnect=False)
 
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
    return os.path.join(IMAGES_DIR, filename)

def check_existence_of_image(filename):
    path = _get_image_path(filename)
    return os.path.exists(path)
    
def list_images():
    return os.listdir(IMAGES_DIR)

def delete_image(filename):
    #TODO does deleting a displayed image require special handling, for now I'm assuming not
    try:
        path = _get_image_path(filename)
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        log_error(f"Failed to delete {file_path}. Reason: {e}")

def delete_sd_files_with_filter(names_filter_set):
    """ Delete all files in the IMAGES_DIR, except those found in the names_filter_set """
    if not os.path.exists(IMAGES_DIR):
        return
    for filename in list_images():
        if filename not in names_filter_set:
            delete_image(filename) 

def write_text(msg, error):
    if g_graphics:
      WIDTH, HEIGHT = g_graphics.get_bounds()
      g_graphics.set_font("bitmap8")
      g_graphics.set_pen(inky_frame.WHITE)
      g_graphics.clear()
      g_graphics.set_pen(inky_frame.RED if error else inky_frame.YELLOW)
      # g_graphics.measure_text(text, scale, spacing, fixed_width)
      g_graphics.text(mag, 10, 10, WIDTH-30, scale=3)
      

def _display_jpeg(filename):
    if not g_graphics:
        return
    path = _get_image_path(filename)
    try:
        gc.collect()
        # Used in the xkcd example, not sure if it is necessary
        #g_graphics.set_pen(inky_frame.WHITE)
        #g_graphics.clear()
        # TODO in the example this was a singleton, but that seems unncessary
        j = jpegdec.JPEG(g_graphics)
        j.open_file(path)
        j.decode(0, 0, jpegdec.JPEG_SCALE_FULL)
        g_graphics.update()
    except Exception as e:
        log_error(f"CRITICAL ::i An error occurred during loading of json map: {e}")

def display_image_by_time():
    """
       The goal is to rotate an image based on teh hour, but avoid certain images only displaying during night time.
       HOUR_LOWER_BOUND + HOUR_UPPER_BOUND configure the waking hours 0 -23 inclusive
       In combinatio nwith an number of hours since the begining of the month, we module against hte number of aivlable images
    """
    monthly_hour_epoc = 0
    year, _, _, days, hours, _, _, _ = RTC().datetime().astimezone(ZoneInfo(TIMEZONE))
    if year < 2023:
      # Connect to network
       inky_frame.set_time()  # Sets both the Inky and Pico RTC
 
    if hours < HOUR_LOWER_BOUND:
       monthly_hour_epoc = 0 
    elif hours > HOUR_UPPER_BOUND:
       monthly_hour_epoc = HOUR_UPPER_BOUND
    else:
       monthly_hour_epoc = hours

    if days > 0:
       monthly_hour_epoc += (days - 1)*24
    sorted_paths = sorted(list_images())
    if len(sorted_paths) == 0:
       log_warning("No images to display")
       return
    idx = (monthly_hour_epoc + g_idx_offset) % len(available_images)
    filename = sorted_paths[idx]
    _display_jpeg(filename)

def _download_urequest(url, path, max_redirects=5):
    """
        Complex overloading because this supports two usecases in order to reuse the 30X handling code
        @returns (body, status)
          - status -> a boolean success vs failure
          if path = None then body will contkain the response body ie the content
          if path is not None then body = "" aka empty string
          Note if status == False then body always = ""
    """

    redirect_count = 0
    current_url = url
    response = None
    while redirect_count <= max_redirects:
        # MicroPython's urlopen doesn't accept 'timeout' in old versions,
        # but modern urequest handles basic GET via string url.
        # Note: urequest uses HTTP/1.0, so 'stream=True' is implied via raw reading.
        try:
            response = urequest.urlopen(current_url)
        except Exception as e:
            log_error(f"Connection failed: {e}")
            return ("", False)

        # Extract status code. MicroPython objects vary; check for status or code attribute
        status_code = getattr(response, "status", getattr(response, "code", 200))
        # MicroPython doesn't have response.raise_for_status() natively
        if 400 <= status_code < 600:
            log_error(f"HTTP ErrorL {status_code} while attempting google drive download.")
            return ("", False)

        # Handle 30X Redirects manually
        if 300 <= status_code < 400:
            # Look for the 'Location' header to find the redirect target
            # MicroPython headers are usually case-sensitive inside a dictionary or list
            headers = response.headers
            location = None

            if hasattr(headers, "get"):
                location = headers.get("Location") or headers.get("location")
            else:
                # Fallback if headers is a raw string/list list structure
                for header in headers:
                    if header.lower().startswith("location:"):
                        location = header.split(":", 1)[1].strip()
                        break

            if not location:
                log_error(f"Redirect status {status_code} received but no Location header found.")
                return ("", False)

            # Close current response before opening a new connection to save RAM
            response.close()
            
            # Handle relative redirect URLs
            if location.startswith("/"):
                # Simple base URL reconstruction
                protocol, _, rest = current_url.split("/", 2)
                domain = rest.split("/", 1)[0]
                current_url = f"{protocol}//{domain}{location}"
            else:
                current_url = location

            redirect_count += 1
            continue  # Loop back to request the new URL
        else:
            # If it's not a 30x redirect, break out of the loop
            break
    else:
        log_error("Too many redirects while attempting google drive download")
        return ("", False)

    body = None
    try:
        if path:
            # MicroPython urlopen returns an object that acts as a stream
            # or has a .raw socket stream interface
            stream = getattr(response, "raw", response)
            # We are streaming to a file
            body = ""
            with open(path, 'wb') as file:
                while True:
                    chunk = stream.read(CHUNK_SIZE)
                    if not chunk: # End of stream
                        break
                    file.write(chunk)

                    # Proactively call garbage collection during heavy I/O
                    gc.collect()
            stream.close()
        else:
            # We are reading contents directly into a variable
            body = response.read().decode("utf-8")
            gc.collect()
    finally:
        response.close()

    return (body, body is not None)

def download_image(filename, url):
    path = _get_image_path(filename)
    if os.path.exists(path):
       return False
    (_, result) = _download_urequest(url, path)
    if not result:
      #Attempt to cleanup incase of mid download problems, not 100% robust, but should be pretty stable
      delete_image(filename)
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
       download_image(name, img_entry['url'])

################
# LED controls #
################
def reset_all_leds():
    for btn in LED_BUTTONS:
        btn.led_off()

def cycle_led(btn, delay_in_seconds=0.3, blink=True):
    _blink_delay_in_seconds = 0.1
    btn.led_on()
    if blink:
        time.sleep(_blink_delay_in_seconds)
        btn.led_toggle()
        time.sleep(_blink_delay_in_seconds)
        btn.led_toggle()
    time.sleep(delay_in_seconds)
    btn.led_toggle()
    
    
def cycle_all_leds(delay_in_seconds=0.3, blink=True):
    """ Cycle through each button, this takes 5x delay_in_seconds + 10x _blink_delay_in_seconds if blink is enabled """
    for btn in LED_BUTTONS:
        cycle_led(btn, delay_in_seconds, blink)

#############
# Main Loop #
#############
def main_loop():
    hardware_init()
    reset_all_leds()
    cycle_all_leds()

    while True:
        # Step 0: Handle Buttons 
        if inky_frame.button_a.read():
            # Increment to the next picture
            g_idx_offset += 1
        elif inky_frame.button_b.read():
            # Increment a random next picture
            img_cnt = max(len(list_images()) - 1, 0)
            g_idx_offset += random.randint(0, img_cnt)
            #g_idx_offset += random.randrange(len(list_images()))
        elif inky_frame.button_c.read():
            pass 
        elif inky_frame.button_d.read():
            # Attempt to reconnect to wifi
            wifi_connect(disconnect=True)
        elif inky_frame.button_e.read():
            # Reset - delete images directory and attempt to redownload
            g_idx_offset = 0
            delete_sd_files_with_filter(set())

        # Step 1: Cleanup old images and add new ones
        json_body = load_json_body(JSON_MAP_URL)
        if json_body:
            process_json_body(json_body)
        else:
            log_warning("Unable to downlaod new pictures due to failure of load_json_body")

        # Step 2: Select which image to display
        display_image_by_time()

        # Step 3: Go to sleep
        inky_frame.sleep_for(PERIOD_IN_MINUTES)
        #turn_off() shouldn't be necessary as the docs claim sleep_for handles this
        #inky_frame.turn_off()  


if __name__ == "__main__":
    """ See testbench.py for manual testing off the device. """
    main_loop()
