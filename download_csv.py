import kagglehub
import os
import shutil

# Download dataset using KaggleHub
path = kagglehub.dataset_download(
    "thoughtvector/customer-support-on-twitter"
)

print("Downloaded to:", path)

# Your desired destination
destination = r"D:\Varu_info\Hiver\reports"

# Create destination folder if it doesn't exist
os.makedirs(destination, exist_ok=True)

# Copy all downloaded files/folders to destination
for item in os.listdir(path):
    source = os.path.join(path, item)
    target = os.path.join(destination, item)

    if os.path.isdir(source):
        shutil.copytree(source, target, dirs_exist_ok=True)
    else:
        shutil.copy2(source, target)

print("\nFiles copied to:", destination)

# Display files and sizes
for item in os.listdir(destination):
    full_path = os.path.join(destination, item)

    if os.path.isfile(full_path):
        size_mb = os.path.getsize(full_path) / (1024 * 1024)
        print(f"FILE : {item} | {size_mb:.2f} MB")
    else:
        print(f"DIR  : {item}")
        print("      ", os.listdir(full_path)[:10])