### Google Infrastructure Setup
1. Configure 3 folders - incoming, outgoing, error, Note their folderIds
1. Add an empty file called json_map.json, Note its fileId
1. Sharing
   * Make json_map.json and outgoing avialable to anyone withthe link
   * Share the incoming folder with your family
1. Google App Script Setup 
   1. Create a Google App Script and copy paste from repo
   1. Add a file to that project called "jpeg-js" copy jpeg-js.gs from this repo
   1. Update with the three folderIds and the one fileId
   1. Make sure that the main funciton is "process_incoming"
   1. Schedule a time based trigger to run every X minutes
   1. Test the system by Uploading a file to incoming and wait for the script to run and move it to outgoing


### Inky Setup
1. Warning - some sdcards were very finicky
1. Copy example_config.ini to config.ini on the sd card and review all values, Note some have no defaults and need info from the Google Drive steps
1. Attach a SD card to the Inky, this code depends on there being one available
1. Upload the main.py and sdcard.py scripts to the Inky Picture Frame
1. QA, it is now your time to shine ¯\_(ツ)_/¯ 


### Basic Manual
1. Button 1 - Advances to the next picture
1. Button 2 - Advances to a random picture
1. Button 3 - Currently unused 
1. Button 4 - Drop the wifi connection and attempt to reconnect. *Experimental*
1. Button 5 - Rests the system, deleting all local images and attempts to redownload them


### Testing on PC
1. Make sure you have the Google Infrastructure Setup, see above
1. Make a copy of exmaple_config.ini `cp example_config.ini config.ini` and fill in at least json_map_url
1. Modify testbench.py by tailoring the `if __name__ == "__main__":` portion as you like.
1. Run it `python3 testbench.py`


### Rebuilding jpeg.js.gs
This file is the stripped version of the jpeg-js npm with its buffer dependency, packaged in a way that avoids using imports for  AppScript compatability.
1. Goto https://bundlejs.com/
1. Type buffer and get the one that is around verison 6.0.3
1. Click "Add Module"
1. Modify the Input window to look similar to the code snippit
1. Click build
1. Goto the output and copy paste it all into a new file.
1. Look at the very end of it and put a newline before globalThis.Buffer =
1. Modify this new line to assign globalThis.Buffer to whatever was being exported. See current file for an exmaple.
1. Goto https://bundlejs.com/ in a new window, the last one is tainted and cannot be trusted
1. Type jpeg-js and get the one that is around verison 0.4.4
1. Click "Add Module"
1. Modify the Input window to look similar to the second code snippit
1. Click build
1. Goto the output and copy paste it at the end of the same file from the Buffer module steps
1. Look at the very end of it and a newline "globalThis.jpeg = {encode:AA(), decode:BB()}"
1. Note that AA and BB are whatever the variables being exported as encode and decode were, we are creating a global object called jpeg with an encode and decode method on it that our main javascript code will call.



```
export { Buffer } from "buffer@6.0.3";
globalThis.Buffer = Buffer;
```

```

```

### Python venv
```
python3 -m venv myenv
source myenv/bin/activate
deactivate
```
