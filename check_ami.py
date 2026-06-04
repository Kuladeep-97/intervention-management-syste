import os
import sys
import boto3

def load_env(filepath):
    config = {}
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
    config = load_env(".env.deployment")
    aws_key = config.get("AWS_ACCESS_KEY_ID")
    aws_secret = config.get("AWS_SECRET_ACCESS_KEY")
    region = config.get("AWS_DEFAULT_REGION", "ap-south-1")
    ami_id = config.get("EC2_AMI_ID")
    
    session = boto3.Session(
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret,
        region_name=region
    )
    ec2_client = session.client("ec2")
    
    try:
        response = ec2_client.describe_images(ImageIds=[ami_id])
        if response["Images"]:
            img = response["Images"][0]
            print(f"AMI ID: {ami_id}")
            print(f"Name: {img.get('Name')}")
            print(f"Description: {img.get('Description')}")
            print(f"Platform: {img.get('Platform')}")
            print(f"Platform Details: {img.get('PlatformDetails')}")
            print(f"OwnerId: {img.get('OwnerId')}")
        else:
            print("No images found.")
    except Exception as e:
        print(f"Error describing AMI: {e}")

if __name__ == "__main__":
    main()
