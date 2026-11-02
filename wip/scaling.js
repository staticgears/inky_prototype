/**
 * Takes a JPEG file on Google Drive and downscales+overwrites) it to a target maximum width/height.
 * IMPORTANT :: Make sure the Advanced Drive Service is turned on
 * 1. On the left pane of your Apps Script editor, click the + next to Services.
 * 2. Find and select Drive API.
 * 3. Click Add.
 * 
 * Note: To my knowledge a Spectra 7.3 has dimensions 800x480
 * @param {File} originalFile - The JPEG file on Google Drive.
 * @param {number} maxPixelDimension - The maximum allowable width or height (e.g., 1024).
 * @return {bool} if scaling occured 
 */
function downscaleAndOverwriteJpegFile(orignalFile, maxPixelDimension = 800) {
  const imageBlob = originalFile.getBlob();
  
  // 1. Create a temporary Google Slides presentation to act as our processing canvas
  // Google Slides treats 1 inch as 72 points, and modern screens map roughly 1 point = 1 pixel here.
  const tempPresentation = SlidesApp.create("Temp_Image_Processor");
  const slide = tempPresentation.getSlides()[0];
  
  // 2. Insert the image onto the slide to read its native dimensions
  const slideImage = slide.insertImage(imageBlob);
  const origWidth = slideImage.getWidth();
  const origHeight = slideImage.getHeight();
  
  // 3. Calculate the downscaled dimensions preserving aspect ratio
  let newWidth = origWidth;
  let newHeight = origHeight;
  
  if (origWidth > maxPixelDimension || origHeight > maxPixelDimension) {
    if (origWidth > origHeight) {
      newWidth = maxPixelDimension;
      newHeight = Math.round((origHeight * maxPixelDimension) / origWidth);
    } else {
      newHeight = maxPixelDimension;
      newWidth = Math.round((origWidth * maxPixelDimension) / origHeight);
    }
  } else {
    // If the image is already smaller than the max dimension, clean up and exit
    tempPresentation.setTrashed(true);
    return false;
  }
  
  // 4. Update the visual element size on the slide
  slideImage.setWidth(newWidth);
  slideImage.setHeight(newHeight);
  
  // 5. Force Google Slides to flush changes to its servers
  tempPresentation.saveAndClose();
  
  // 6. Use UrlFetchApp to extract the rendered slide thumbnail page as a fresh compressed JPEG
  const presentationId = tempPresentation.getId();
  const slideId = slide.getObjectId();
  
  // We construct the slide export URL specifying our targeted downscaled pixel width
  const exportUrl = `https://google.com{presentationId}/export/jpeg?id=${presentationId}&pageid=${slideId}&width=${newWidth}`;
  
  const options = {
    headers: {
      Authorization: "Bearer " + ScriptApp.getOAuthToken()
    }
  };
  
  // 7. Fetch the new downscaled image blob
  const scaledBlob = UrlFetchApp.fetch(exportUrl, options).getBlob();
  let updatedName = `downscaled_${originalFile.getName()}`
  scaledBlob.setName(updatedName);
  // originalFile.setName(updatedName);
  
  // 8. Save the downscaled image to the same folder as the original file
  Drive.Files.update({}, originalFile.getId(), scaledBlob);
  
  // 9. Clean up by deleting the temporary presentation
  DriveApp.getFileById(presentationId).setTrashed(true);
  
  Logger.log(`Successfully downscaled from ${origWidth}x${origHeight} to ${newWidth}x${newHeight}`);
  return true;
}

/**
 * Takes a JPEG file on Google Drive, downscales its dimensions, forces a lower quality
 * compression profile via Drive's thumbnail renderer, and overwrites the original.
 * 
 * IMPORTANT :: Make sure the Advanced Drive Service is turned on
 * 1. On the left pane of your Apps Script editor, click the + next to Services.
 * 2. Find and select Drive API.
 * 3. Click Add.
 * 
 * Note: To my knowledge a Spectra 7.3 has dimensions 800x480
 * 
 * @param {File} originalFile - The original JPEG file on Google Drive.
 * @param {number} maxPixelDimension - The maximum allowable width or height (e.g., 800).
 */
function compressAndOverwriteJpegFile(originalFile, maxPixelDimension = 800) {
  // 1. Check dimensions
  const origWidth = parseInt(originalFile.imageMediaMetadata.width);
  const origHeight = parseInt(originalFile.imageMediaMetadata.height);
  
  // 2. Calculate the target downscaled dimensions preserving aspect ratio
  let targetWidth = origWidth;
  
  if (origWidth > maxPixelDimension || origHeight > maxPixelDimension) {
    if (origWidth > origHeight) {
      targetWidth = maxPixelDimension;
    } else {
      targetWidth = Math.round((origWidth * maxPixelDimension) / origHeight);
    }
  } else {
    // If the image is already visually smaller, use its current width to trigger quality reduction anyway
    targetWidth = origWidth;
  }
  
  // 3. Retrieve Google Drive's native thumbnail generation link for this file
  const baseThumbnailUrl = originalFile.thumbnailLink;
  if (!baseThumbnailUrl) {
    throw new Error("Could not retrieve the thumbnail link. Ensure the file is a valid image.");
  }
  
  // 4. Manipulate the URL parameter to specify our exact target width (=sXXXX)
  // Google Drive automatically scales the height proportionately and applies a high-compression pass.
  const optimizedImageUrl = baseThumbnailUrl.replace(/=s\d+/, `=s${targetWidth}`);
  
  // 5. Fetch the heavily compressed, downscaled image blob using authentication
  const options = {
    headers: {
      Authorization: "Bearer " + ScriptApp.getOAuthToken()
    },
    muteHttpExceptions: true
  };
  
  const response = UrlFetchApp.fetch(optimizedImageUrl, options);
  const compressedBlob = response.getBlob();
  
  // 6. Overwrite the original file binary data with our optimized blob
  Drive.Files.update({}, originalFile.getId(), compressedBlob);
  
  Logger.log(`Successfully compressed image! File updated to maximum boundary of ${maxPixelDimension}px with reduced file quality.`);
}

// --- Example Execution ---
function runDownscaleTest() {
  const targetFileId = "YOUR_LARGE_JPEG_FILE_ID_HERE";
  const targetFile = Drive.Files.get(targetFileId);
  // Resize so that its longest side is at most X pixels
  const wasScaled = downscaleAndOverwriteJpegFile(targetFile, 800); 
  #const wasScaled = compressAndOverwriteJpegFile(targetFile, 800)
}

