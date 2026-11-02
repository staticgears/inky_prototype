### Google Infrastructure Setup
1. Configure 3 folders - incoming, outgoing, error, Note their folderIds
1. Add an empty file called json_map.json, Note its fileId
1. Sharing
   * Make json_map.json and outgoing avialable to anyone withthe link
   * Share the incoming folder with your family
1. Google App Script Setup 
   1. Create a Google App Script and copy paste from repo
   1. Update with the three folderIds and the one fileId
   1. Make sure that the main funciton is "process_incoming"
   1. Schedule a time based trigger to run every X minutes
   1. Test the system by Uploading a file to incoming and wait for the script to run and move it to outgoing


### Inky Setup
1. Copy example_config.ini to config.ini and review all values, Note some have no defaults and need info from the Google Drive steps
1. Attach a SD card to the Inky, this code depends on there being one available
1. Upload the main python script to the Inky Picture Frame
1. QA, it is now your time to shine ¯\_(ツ)_/¯ 


### Basic Manual
1. Button 1 - Advances to the next picture
1. Button 2 - Advances to a random picture
1. Button 3 - Currently unused 
1. Button 4 - Currently unused 
1. Button 5 - Rests the system, deleting all local images and attempts to redownload them


### Testing on PC
1. Make sure you have the Google Infrastructure Setup, see above
1. Make a copy of exmaple_config.ini `cp example_config.ini config.ini` and fill in at least json_map_url
1. Uncomment the inky_stubs import in main.py and then tailor the `if __name__ == "__main__":` portion as you like.


### Python venv
```
python3 -m venv myenv
source myenv/bin/activate
deactivate
```

