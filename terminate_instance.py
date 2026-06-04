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
    
    session = boto3.Session(
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret,
        region_name=region
    )
    ec2_client = session.client("ec2")
    
    instance_id = "i-037d11c628532d950"
    print(f"=== Terminating Old Instance: {instance_id} ===")
    
    try:
        ec2_client.terminate_instances(InstanceIds=[instance_id])
        print(f"[OK] Termination request sent successfully!")
    except Exception as e:
        print(f"Error terminating instance: {e}")

if __name__ == "__main__":
    main()
