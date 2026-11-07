import gc, os
CHUNK_SIZE = 1024

def reduce_jpeg_quality_in_place(filepath, compression_factor=2):
    """
    Reduces JPEG quality directly on the file stream by scaling the 
    Quantization Tables (DQT). Same dimensions, minimal memory overhead.
    
    :param compression_factor: Integer >= 1. Higher = Lower Quality/Smaller Size.
    """

    tmpfile = filepath + ".tmp"
    os.rename(filepath, tmpfile) 
    input_path = tmpfile   
    output_path = filepath   
    with open(input_path, 'rb') as infile, open(output_path, 'wb') as outfile:
        while True:
            # Explicitly clear garbage on loop cycles
            gc.collect()
            
            # Read a small window of data
            chunk = infile.read(CHUNK_SIZE)
            if not chunk:
                break
                
            # Scan the chunk for the Define Quantization Table (DQT) marker: 0xFFDB
            # A JPEG marker is 2 bytes long.
            idx = 0
            while idx < len(chunk) - 4:
                if chunk[idx] == 0xFF and chunk[idx+1] == 0xDB:
                    # Found DQT marker!
                    # Next 2 bytes define the length of the DQT payload
                    dqt_length = (chunk[idx+2] << 8) + chunk[idx+3]
                    
                    # Read the full table if it overflows the current chunk
                    remaining_payload = dqt_length - (len(chunk) - idx - 2)
                    if remaining_payload > 0:
                        chunk += infile.read(remaining_payload)
                    
                    # Convert chunk to a mutable bytearray to modify values in-place
                    mutable_chunk = bytearray(chunk)
                    
                    # The table data starts after 0xFFDB (2 bytes) + Length (2 bytes) + Identifier (1 byte)
                    table_start = idx + 5
                    table_end = table_start + 64 # JPEG quantization tables are 8x8 matrix (64 bytes)
                    
                    # Scale down the precision values to lower the quality
                    for i in range(table_start, min(table_end, len(mutable_chunk))):
                        # Multiply the quantization value (higher value = coarser compression)
                        scaled_value = mutable_chunk[i] * compression_factor
                        mutable_chunk[i] = min(scaled_value, 255) # Cap at 8-bit max
                    
                    chunk = bytes(mutable_chunk)
                    idx += dqt_length + 2
                else:
                    idx += 1
            
            # Pipe the processed stream chunk straight to storage
            outfile.write(chunk)
            try:
                os.remove(tmpfile)
            except OSError:
                pass

if __name__ == "__main__":
    reduce_jpeg_quality_in_place("test.jpg", compression_factor=2)
