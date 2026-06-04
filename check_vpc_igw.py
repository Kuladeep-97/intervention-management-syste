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
    vpc_id = "vpc-095e7cd993a742f57"
    
    print(f"=== Inspecting Internet Gateways for VPC: {vpc_id} ===")
    
    try:
        # Check attached IGWs
        igws = ec2_client.describe_internet_gateways(
            Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}]
        )
        
        if igws["InternetGateways"]:
            igw = igws["InternetGateways"][0]
            igw_id = igw["InternetGatewayId"]
            print(f"[OK] Found active Internet Gateway: {igw_id}")
            
            # Since an IGW exists, let's check all route tables to see if one has it
            print("\n--- Listing All Route Tables in VPC ---")
            rts = ec2_client.describe_route_tables(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )
            for rt in rts["RouteTables"]:
                rt_id = rt["RouteTableId"]
                is_main = any(assoc.get("Main") for assoc in rt.get("Associations", []))
                print(f"Route Table: {rt_id} (Main: {is_main})")
                for route in rt["Routes"]:
                    dest = route.get("DestinationCidrBlock")
                    gateway = route.get("GatewayId")
                    state = route.get("State")
                    print(f"  - Route: {dest} -> {gateway} (State: {state})")
                    
                # Let's fix the default route in the broken route table!
                broken_rt_id = "rtb-0cbb5edca7ca06fdd"
                if rt_id == broken_rt_id:
                    print(f"\nAttempting to repair default route in {broken_rt_id} to point to {igw_id}...")
                    try:
                        # Delete the broken default route
                        try:
                            ec2_client.delete_route(
                                RouteTableId=broken_rt_id,
                                DestinationCidrBlock="0.0.0.0/0"
                            )
                        except Exception:
                            pass
                        
                        # Create a valid route to the IGW
                        ec2_client.create_route(
                            RouteTableId=broken_rt_id,
                            DestinationCidrBlock="0.0.0.0/0",
                            GatewayId=igw_id
                        )
                        print("REPAIR SUCCESSFUL! Default route to Internet Gateway created!")
                    except Exception as repair_err:
                        print(f"[ERROR] Failed to repair route table: {repair_err}")
        else:
            print(f"[ERROR] No Internet Gateway is attached to VPC: {vpc_id}!")
            
            # Let's see if there is another VPC that has an attached Internet Gateway
            print("\n--- Searching other VPCs in region ---")
            all_vpcs = ec2_client.describe_vpcs()
            for vpc in all_vpcs["Vpcs"]:
                v_id = vpc["VpcId"]
                is_default = vpc.get("IsDefault", False)
                v_igws = ec2_client.describe_internet_gateways(
                    Filters=[{"Name": "attachment.vpc-id", "Values": [v_id]}]
                )
                has_igw = len(v_igws["InternetGateways"]) > 0
                print(f"VPC: {v_id} (Default: {is_default}, Has Attached IGW: {has_igw})")
                
    except Exception as e:
        print(f"Error describing networking: {e}")

if __name__ == "__main__":
    main()
