// Configuration
// Step 1: Create three folders for incoming, outgoing, and error files
// Step 2: Create an empty json file for the JsonMap
// Step 3: Configure these 4 ids in this script
// Step 4: Ensure that JsonMap and outgoingFolder are set to public for anyone with the URL
// Step 5: Share the incomingFolder with people who you want to allow to uplaod files
// Step 6: Enable Advanced Drive Service if using scaling - Left menu, Services -> Drive Api -> Add

const jsonMapId = "TODO";
const incomingFolderId = "TODO";

const outgoingFolderId = "TODO";
const outgoingFolder = DriveApp.getFolderById(outgoingFolderId);

const errorFolderId = "TODO";
const errorFolder = DriveApp.getFolderById(errorFolderId);

function process_incoming() {
  try {
    let incomingFiles = getFilesInFolder(incomingFolderId);
    if (incomingFiles.length > 0) {
      incomingFiles.forEach((file) => {
        process_file(file);
      })
    }
    updateJsonMap()
  } catch (error) {
    console.error(Utilities.formatString("Error in process_incoming:: Error: %s. Stack trace: %s", error.message, error.stack));
    throw error;
  }
}

function updateJsonMap() {
  let activeFiles = getFilesInFolder(outgoingFolderId);
  const dataArray = activeFiles.map((item, _) => ({
    name: item.getName(),
    url: `https://drive.google.com/uc?export=view&id=${item.getId()}`
  }));
  const jsonString = JSON.stringify(dataArray, null, 2);
  const file = DriveApp.getFileById(jsonMapId);
  file.setContent(jsonString);
}

function process_file(file) {
  let fileId = file.getId();
  try {
    const name = file.getName();
    const mimeType = file.getMimeType();
    const url = `https://drive.google.com/thumbnail?id=${fileId}&sz=w1000`;
    if (is_heif(name, mimeType) || is_png(name, mimeType)) {
      handle_conversion(name, url);
      file.setTrashed(true);
    } else if(is_jpeg(name, mimeType)) {
      file.setName(normalise_filename(file.getName()));
      file.moveTo(outgoingFolder);
    } else {
      throw new Error("Unsupported file type name: \'%s\' mime-type:'%s\'", name, mimeType);
    }    
  } catch (error) {
    console.error(Utilities.formatString("Error in process_file:: id:%s Error: %s. Stack trace: %s", fileId, error.message, error.stack));
    file.moveTo(errorFolder);
    //throw error;
  }
}

function is_jpeg(name, mimeType) {
  return (name.includes("jpg") || name.includes("jpeg") || mimeType == "image/jpeg");
}

function is_png(name, mimeType) {
  return (name.includes("png") || mimeType == "image/png");
}

function is_heif(name, mimeType) {
  return (name.includes("heic") || name.includes("heif") || mimeType == "image/heic");
}

function handle_conversion(name, url) {
  const blob = UrlFetchApp.fetch(url, { headers: { authorization: "Bearer " + ScriptApp.getOAuthToken() } }).getBlob().getAs("image/jpeg");
  outgoingFolder.createFile(blob.setName(normalise_filename(name)));
}

function getFilesInFolder(folderId) {
  const filesList = [];
  
  try {
    const folder = DriveApp.getFolderById(folderId);    
    const filesIterator = folder.getFiles();
    
    while (filesIterator.hasNext()) {
      const file = filesIterator.next();
      filesList.push(file);
    }
    return filesList;
  } catch (error) {
    console.error(Utilities.formatString("Error retrieving files for folder %s: %s", folderId, error.stack));
    throw error;
  }
}

function normalise_filename(input) {
  // 1. Illegal characters for filenames (\ / ? < > \ : * | ")
  const illegalRe = /[\/\?<>\\:\*\|":]/g;
  
  // 2. Control characters (0x00–0x1f and 0x80–0x9f)
  const controlRe = /[\x00-\x1f\x80-\x9f]/g;
  
  // 3. Unix reserved filenames (. and ..)
  const reservedRe = /^\.+$/;
  
  // 4. Windows reserved filenames (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
  const windowsReservedRe = /^(con|prn|aux|nul|com[0-9]|lpt[0-9])(\..*)?$/i;
  
  // 5. Windows trailing periods/spaces
  const windowsTrailingRe = /[\s\.]+$/g;

  // 5. Whitespace
  const whitespace = /\s+/g;

  var newName = (input.split(".")[0]).toLocaleLowerCase()
    .replace(illegalRe, '')
    .replace(controlRe, '')
    .replace(reservedRe, '')
    .replace(windowsReservedRe, '')
    .replace(windowsTrailingRe, '')
    .replace(whitespace, '');
  newName = newName  + ".jpg"
  return newName
}
