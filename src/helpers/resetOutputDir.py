import os
import shutil

# Create output directory or clean it if it exists
def resetOutputDir():
    """
    This function resets the output directory by deleting all files in it.
    If the directory does not exist, it creates a new one.
    """
    # Define the output directory
    output_dir = "output"
    if os.path.exists(output_dir):
        # Delete all files in the output directory
        for filename in os.listdir(output_dir):
            file_path = os.path.join(output_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")
    else:
        # Create the output directory
        os.makedirs(output_dir)