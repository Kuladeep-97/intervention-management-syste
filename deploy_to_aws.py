import os
import sys
import time
import boto3
from botocore.exceptions import ClientError

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
    print("=== Starting IMS AWS EC2 Provisioner ===")
    config = load_env(".env.deployment")
    
    # Extract config details
    aws_key = config.get("AWS_ACCESS_KEY_ID")
    aws_secret = config.get("AWS_SECRET_ACCESS_KEY")
    region = config.get("AWS_DEFAULT_REGION", "ap-south-1")
    instance_type = config.get("EC2_INSTANCE_TYPE", "t3.medium")
    ami_id = config.get("EC2_AMI_ID")
    key_name = config.get("EC2_KEY_PAIR_NAME")
    private_key_path = config.get("EC2_PRIVATE_KEY_PATH")
    
    # Check for placeholder values
    if not aws_key or not aws_secret or not key_name or "YOUR_" in aws_key or "YOUR_" in aws_secret or "YOUR_" in key_name:
        print("\n[ERROR] Please configure your real credentials inside '.env.deployment' before running.")
        sys.exit(1)
        
    print("--- Connecting to AWS ---")
    session = boto3.Session(
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret,
        region_name=region
    )
    ec2_client = session.client("ec2")
    ec2_resource = session.resource("ec2")
    
    # 1. Check or Create Security Group
    sg_name = "IMS-Monolithic-SG"
    sg_desc = "Security group for IMS Web Application (HTTP and SSH)"
    sg_id = None
    
    try:
        response = ec2_client.describe_security_groups(GroupNames=[sg_name])
        sg_id = response["SecurityGroups"][0]["GroupId"]
        print(f"[OK] Found existing Security Group: {sg_name} ({sg_id})")
    except ClientError as e:
        if "InvalidGroup.NotFound" in str(e):
            print(f"--- Creating new Security Group: {sg_name} ---")
            try:
                # Get default VPC
                vpcs = ec2_client.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])
                default_vpc_id = vpcs["Vpcs"][0]["VpcId"]
                
                sg = ec2_client.create_security_group(
                    GroupName=sg_name,
                    Description=sg_desc,
                    VpcId=default_vpc_id
                )
                sg_id = sg["GroupId"]
                print(f"[OK] Created Security Group: {sg_name} ({sg_id})")
                
                # Authorize inbound rules
                print("--- Authorizing Port 80 (HTTP) and Port 22 (SSH) ---")
                ec2_client.authorize_security_group_ingress(
                    GroupId=sg_id,
                    IpPermissions=[
                        {
                            "IpProtocol": "tcp",
                            "FromPort": 80,
                            "ToPort": 80,
                            "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "HTTP public access"}]
                        },
                        {
                            "IpProtocol": "tcp",
                            "FromPort": 22,
                            "ToPort": 22,
                            "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "SSH administrative access"}]
                        }
                    ]
                )
                print("[OK] Inbound rules successfully configured!")
            except Exception as create_err:
                print(f"[ERROR] Failed to create Security Group: {create_err}")
                sys.exit(1)
        else:
            print(f"[ERROR] AWS Client Error: {e}")
            sys.exit(1)

    # 2. Launch EC2 Instance
    print(f"\n--- Provisioning EC2 {instance_type} Instance ({ami_id}) ---")
    try:
        instances = ec2_resource.create_instances(
            ImageId=ami_id,
            InstanceType=instance_type,
            MinCount=1,
            MaxCount=1,
            KeyName=key_name,
            SecurityGroupIds=[sg_id],
            TagSpecifications=[
                {
                    "ResourceType": "instance",
                    "Tags": [{"Key": "Name", "Value": "IMS-Monolithic-Host"}]
                }
            ]
        )
        instance = instances[0]
        instance_id = instance.id
        print(f"[OK] Instance state initiated! ID: {instance_id}")
        
        print("Waiting for instance to spin up and acquire Public IP...")
        instance.wait_until_running()
        instance.reload()
        
        public_ip = instance.public_ip_address
        public_dns = instance.public_dns_name
        print(f"\nSUCCESS! Your new EC2 Instance is RUNNING!")
        print(f"==================================================")
        print(f"Instance ID: {instance_id}")
        print(f"Public IPv4: {public_ip}")
        print(f"Public DNS:  {public_dns}")
        print(f"==================================================")
        
    except Exception as launch_err:
        print(f"[ERROR] Failed to launch EC2 instance: {launch_err}")
        sys.exit(1)

    # 3. Output deployment commands
    print("\n--- Deployment Commands ---")
    print("To sync your project files and deploy, run the following commands in your local PowerShell:")
    
    # Handle windows escaping for key path
    clean_key_path = private_key_path.replace("\\", "/")
    
    print("\nCOMMAND 1: Sync Codebase to Remote Server")
    print(f'scp -i "{clean_key_path}" -o StrictHostKeyChecking=no -r ./* ubuntu@{public_ip}:/home/ubuntu/Videoanalytics/')
    
    print("\nCOMMAND 2: Execute Automated Deployment Script")
    print(f'ssh -i "{clean_key_path}" -o StrictHostKeyChecking=no ubuntu@{public_ip} "chmod +x /home/ubuntu/Videoanalytics/deployment/setup_host.sh && /home/ubuntu/Videoanalytics/deployment/setup_host.sh"')
    
    print("\nAfter execution, open your browser and navigate to:")
    print(f"http://{public_ip}/")
    print("==================================================")

if __name__ == "__main__":
    main()
