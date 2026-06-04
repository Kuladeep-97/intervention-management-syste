import os
import sys
import boto3

def load_env(filepath):
    config = {}
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found!")
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
    print(f"=== Diagnosing EC2 Instance: {instance_id} ===")
    
    try:
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        inst = response["Reservations"][0]["Instances"][0]
        
        print(f"State: {inst['State']['Name']}")
        print(f"Public IP: {inst.get('PublicIpAddress')}")
        print(f"VPC ID: {inst.get('VpcId')}")
        print(f"Subnet ID: {inst.get('SubnetId')}")
        print(f"Key Name: {inst.get('KeyName')}")
        
        # Describe Security Group Rules
        sg_id = inst["SecurityGroups"][0]["GroupId"]
        print(f"\n--- Security Group: {sg_id} Rules ---")
        sgs = ec2_client.describe_security_groups(GroupIds=[sg_id])
        for sg in sgs["SecurityGroups"]:
            print(f"Group Name: {sg['GroupName']}")
            print("Inbound Rules (IpPermissions):")
            for permission in sg["IpPermissions"]:
                from_port = permission.get("FromPort")
                to_port = permission.get("ToPort")
                protocol = permission.get("IpProtocol")
                ranges = [r["CidrIp"] for r in permission.get("IpRanges", [])]
                print(f"  - Protocol: {protocol}, Ports: {from_port}-{to_port}, Allowed CIDRs: {ranges}")
                
        # Describe Subnet to check if it has MapPublicIpOnLaunch enabled
        subnet_id = inst.get("SubnetId")
        if subnet_id:
            subnets = ec2_client.describe_subnets(SubnetIds=[subnet_id])
            subnet = subnets["Subnets"][0]
            print(f"\n--- Subnet ID: {subnet_id} details ---")
            print(f"CIDR Block: {subnet['CidrBlock']}")
            print(f"MapPublicIpOnLaunch: {subnet.get('MapPublicIpOnLaunch')}")
            
            # Check Route Table
            route_tables = ec2_client.describe_route_tables(
                Filters=[{"Name": "association.subnet-id", "Values": [subnet_id]}]
            )
            if not route_tables["RouteTables"]:
                # Check main route table of VPC
                route_tables = ec2_client.describe_route_tables(
                    Filters=[{"Name": "vpc-id", "Values": [inst.get("VpcId")]}]
                )
            
            print(f"\n--- Route Table Details ---")
            for rt in route_tables["RouteTables"]:
                print(f"Route Table: {rt['RouteTableId']}")
                for route in rt["Routes"]:
                    dest = route.get("DestinationCidrBlock")
                    gateway = route.get("GatewayId")
                    state = route.get("State")
                    print(f"  - Destination: {dest}, Gateway/Target: {gateway}, State: {state}")
                    
    except Exception as e:
        print(f"Error during diagnostics: {e}")

if __name__ == "__main__":
    main()
