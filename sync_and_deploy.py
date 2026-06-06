import os
import sys
import zipfile
import subprocess
import time
import boto3

def load_env(filepath):
    config = {}
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found! Please create it based on the template.")
        sys.exit(1)
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                config[key.strip()] = val.strip()
    return config

def main():
    print("=== Starting IMS Codebase Sync & Deploy ===")
    config = load_env(".env.deployment")
    
    aws_key = config.get("AWS_ACCESS_KEY_ID")
    aws_secret = config.get("AWS_SECRET_ACCESS_KEY")
    region = config.get("AWS_DEFAULT_REGION", "ap-south-1")
    private_key_path = config.get("EC2_PRIVATE_KEY_PATH").replace("\\", "/")
    
    print("--- Querying running instance IP from AWS ---")
    session = boto3.Session(
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret,
        region_name=region
    )
    ec2_client = session.client("ec2")
    
    response = ec2_client.describe_instances(
        Filters=[
            {"Name": "instance-state-name", "Values": ["running"]},
            {"Name": "tag:Name", "Values": ["IMS-Monolithic-Host"]}
        ]
    )
    
    instances = []
    for reservation in response["Reservations"]:
        for inst in reservation["Instances"]:
            instances.append(inst)
            
    if not instances:
        print("[ERROR] No running EC2 instance named 'IMS-Monolithic-Host' was found!")
        sys.exit(1)
        
    instance = instances[0]
    public_ip = instance["PublicIpAddress"]
    print(f"[OK] Remote EC2 Public IP acquired: {public_ip}")
    
    archive_name = "project.zip"
    print(f"\n--- Creating clean zipped archive: {archive_name} ---")
    
    exclude_dirs = {
        "venv", ".venv", "node_modules", "output", ".git", "dist", ".vite", "__pycache__"
    }
    exclude_extensions = (
        ".mp4", ".avi", ".mov", ".jpg", ".png", ".zip", ".tar.gz", ".csv", ".pyc", ".ipynb"
    )
    
    with zipfile.ZipFile(archive_name, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk("."):
            # Prevent traversing excluded folders or hidden folders
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]
            
            for file in files:
                file_lower = file.lower()
                if file_lower.endswith(exclude_extensions) or file_lower == ".env.deployment":
                    continue
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, ".")
                zipf.write(file_path, rel_path)
                
    print(f"[OK] Zip compilation complete! Size: {os.path.getsize(archive_name) / (1024*1024):.2f} MB")
    
    # Retry Loop to let EC2 SSH server boot up completely
    max_retries = 6
    retry_delay = 10
    success = False
    
    print("\n--- Connecting to remote EC2 server (with boot retry loop) ---")
    for attempt in range(1, max_retries + 1):
        print(f"Connection attempt {attempt}/{max_retries}...")
        scp_cmd = [
            "scp", "-i", private_key_path,
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=5",
            archive_name,
            f"ubuntu@{public_ip}:/home/ubuntu/"
        ]
        
        result = subprocess.run(scp_cmd)
        if result.returncode == 0:
            print("[OK] scp file upload completed successfully!")
            success = True
            break
        else:
            print(f"SSH port is not ready yet. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            
    if not success:
        print("[ERROR] Failed to establish SSH/SCP connection after multiple retries. Please check your Security Group rules or SSH Key Pair path.")
        sys.exit(1)
        
    print("\n--- Triggering remote extraction and host orchestration ---")
    setup_commands = (
        # Install unzip and docker if needed
        f"sudo apt-get update -y && sudo apt-get install -y unzip docker.io && "
        # Back up any existing .mp4 files so redeploys don't wipe the video
        f"mkdir -p /home/ubuntu/_ims_video_backup && "
        f"find /home/ubuntu/Videoanalytics -maxdepth 2 -name '*.mp4' -exec cp {{}} /home/ubuntu/_ims_video_backup/ \\; 2>/dev/null || true && "
        # Wipe old code and extract fresh codebase
        f"rm -rf /home/ubuntu/Videoanalytics && "
        f"mkdir -p /home/ubuntu/Videoanalytics && "
        f"unzip -o /home/ubuntu/project.zip -d /home/ubuntu/Videoanalytics/ && "
        # Restore backed-up video files (assume input_stream folder)
        f"mkdir -p /home/ubuntu/Videoanalytics/input_stream && "
        f"cp /home/ubuntu/_ims_video_backup/*.mp4 /home/ubuntu/Videoanalytics/input_stream/ 2>/dev/null || true && "
        # Create output directory explicitly
        f"mkdir -p /home/ubuntu/Videoanalytics/output && "
        # Stop existing containers if any
        f"sudo docker stop ims-pipeline-container 2>/dev/null || true && "
        f"sudo docker rm ims-pipeline-container 2>/dev/null || true && "
        # Build and Run Docker Container
        f"cd /home/ubuntu/Videoanalytics && "
        f"sudo docker build -t ims-pipeline . && "
        f"sudo docker run -d --name ims-pipeline-container -p 80:8000 -v /home/ubuntu/Videoanalytics/output:/app/output ims-pipeline"
    )
    
    ssh_cmd = [
        "ssh", "-i", private_key_path,
        "-o", "StrictHostKeyChecking=no",
        f"ubuntu@{public_ip}",
        setup_commands
    ]
    print(f"Executing remote script orchestrator...")
    subprocess.run(ssh_cmd, check=True)
    
    if os.path.exists(archive_name):
        os.remove(archive_name)
        
    print(f"\n==================================================")
    print(f"SUCCESS! IMS Web Application has been deployed to AWS!")
    print(f"Access URL: http://{public_ip}/")
    print(f"==================================================")

if __name__ == "__main__":
    main()
