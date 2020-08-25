# network 
NUM_1=3
NUM_2=4
EXTERNAL_NETWORK_ID="1a841cc5-82dc-4dd4-9447-6f6a7ab6147d"
SUBNET_IP_PREFIX="10.168."
IMAGE_ID="d3cf1b90-f3af-41b1-87d7-97f6035f1109"
FLAVOR_ID="cf2G10G2VCPU"
VPN_PSK="asdfghjkl"

function get_args_colume_value() {
  if [ -n "$1" ] && [ -n "$2" ] ; then 
    SHOW_CMD="${1}" 
    COLUME_NAME="${2}"
    ARGS_VALUE=$($SHOW_CMD | grep -w "$COLUME_NAME" | awk -F '|' '{print $3}' | xargs)
    echo "$ARGS_VALUE"
  fi
}


# network
openstack network create --internal  --provider-network-type vxlan cf-vpn-network-internal-$NUM_1
openstack network create --internal  --provider-network-type vxlan cf-vpn-network-internal-$NUM_2
NET_ID_1=$(get_args_colume_value "openstack network show cf-vpn-network-internal-$NUM_1" "id")
NET_ID_2=$(get_args_colume_value "openstack network show cf-vpn-network-internal-$NUM_2" "id")

# subent
openstack subnet create cf-vpn-internal-subnet-$SUBNET_IP_PREFIX$NUM_1-24 --ip-version 4 --subnet-range $SUBNET_IP_PREFIX$NUM_1.0/24 --allocation-pool start=$SUBNET_IP_PREFIX$NUM_1.1,end=$SUBNET_IP_PREFIX$NUM_1.253 --gateway $SUBNET_IP_PREFIX$NUM_1.254 --network $NET_ID_1 --no-dhcp
openstack subnet create cf-vpn-internal-subnet-$SUBNET_IP_PREFIX$NUM_2-24 --ip-version 4 --subnet-range $SUBNET_IP_PREFIX$NUM_2.0/24 --allocation-pool start=$SUBNET_IP_PREFIX$NUM_2.1,end=$SUBNET_IP_PREFIX$NUM_2.253 --gateway $SUBNET_IP_PREFIX$NUM_2.254 --network $NET_ID_2 --no-dhcp
SUBNET_ID_1=$(get_args_colume_value "openstack subnet show cf-vpn-internal-subnet-$SUBNET_IP_PREFIX$NUM_1-24" "id")
SUBNET_ID_2=$(get_args_colume_value "openstack subnet show cf-vpn-internal-subnet-$SUBNET_IP_PREFIX$NUM_2-24" "id")

# router
openstack router create cf-vpn-router-$NUM_1 --centralized
openstack router create cf-vpn-router-$NUM_2 --centralized
ROUTER_ID_1=$(get_args_colume_value "openstack router show cf-vpn-router-$NUM_1" "id")
ROUTER_ID_2=$(get_args_colume_value "openstack router show cf-vpn-router-$NUM_2" "id")

# router subent
openstack router add subnet $ROUTER_ID_1 $SUBNET_ID_1
openstack router add subnet $ROUTER_ID_2 $SUBNET_ID_2

#router set geteway
neutron router-gateway-set $ROUTER_ID_1 "${EXTERNAL_NETWORK_ID}" 
neutron router-gateway-set $ROUTER_ID_2 "${EXTERNAL_NETWORK_ID}" 

# port
openstack port create cf-vpn-port-$SUBNET_IP_PREFIX$NUM_1-1 --fixed-ip subnet=$SUBNT_ID_1,ip-address=$SUBNET_IP_PREFIX$NUM_1.1 --network $NET_ID_1
openstack port create cf-vpn-port-$SUBNET_IP_PREFIX$NUM_2-1 --fixed-ip subnet=$SUBNT_ID_2,ip-address=$SUBNET_IP_PREFIX$NUM_2.1 --network $NET_ID_2
PORT_ID_1=$(get_args_colume_value "openstack port show cf-vpn-port-$SUBNET_IP_PREFIX$NUM_1-1" "id")
PORT_ID_2=$(get_args_colume_value "openstack port show cf-vpn-port-$SUBNET_IP_PREFIX$NUM_2-1" "id")

# server vm
openstack server create --port $PORT_ID_1 --image $IMAGE_ID --flavor $FLAVOR_ID cf-vpn-vm-$NUM_1
openstack server create --port $PORT_ID_2 --image $IMAGE_ID --flavor $FLAVOR_ID cf-vpn-vm-$NUM_2

# vpn ikepolicy 
neutron vpn-ikepolicy-create --auth-algorithm sha1 --ike-version v1 cf-ikepolicy-$NUM_1;
neutron vpn-ikepolicy-create --auth-algorithm sha1 --ike-version v1 cf-ikepolicy-$NUM_2;
IKE_POLICY_ID_1=$(get_args_colume_value "neutron vpn-ikepolicy-show cf-ikepolicy-$NUM_1" "id")
IKE_POLICY_ID_2=$(get_args_colume_value "neutron vpn-ikepolicy-show cf-ikepolicy-$NUM_2" "id")

# vpn ipsecpolicy
neutron vpn-ipsecpolicy-create --auth-algorithm sha1 --encryption-algorithm aes-128 cf-ipsecpolicy-$NUM_1
neutron vpn-ipsecpolicy-create --auth-algorithm sha1 --encryption-algorithm aes-128 cf-ipsecpolicy-$NUM_2
IPSEC_POLICY_ID_1=$(get_args_colume_value "neutron vpn-ipsecpolicy-show cf-ipsecpolicy-$NUM_1" "id")
IPSEC_POLICY_ID_2=$(get_args_colume_value "neutron vpn-ipsecpolicy-show cf-ipsecpolicy-$NUM_2" "id")

# vpn vpn-service
neutron vpn-service-create $ROUTER_ID_1 $SUBNET_ID_1 --name cf-vpn-service-$NUM_1
neutron vpn-service-create $ROUTER_ID_2 $SUBNET_ID_2 --name cf-vpn-service-$NUM_2
VPN_SERVICE_ID_1=$(get_args_colume_value "neutron vpn-service-show cf-vpn-service-$NUM_1" "id")
VPN_SERVICE_ID_2=$(get_args_colume_value "neutron vpn-service-show cf-vpn-service-$NUM_2" "id")
VPN_SERVICE_V4_IP_1=$(get_args_colume_value "neutron vpn-service-show cf-vpn-service-$NUM_1" "external_v4_ip")
VPN_SERVICE_V4_IP_2=$(get_args_colume_value "neutron vpn-service-show cf-vpn-service-$NUM_2" "external_v4_ip")
#neutron vpn-service-delete $VPN_SERVICE_ID_1 
#neutron vpn-service-delete $VPN_SERVICE_ID_2

# vpn ipsec-site-connection
echo neutron ipsec-site-connection-create --vpnservice-id $VPN_SERVICE_ID_1 --ikepolicy-id $IKE_POLICY_ID_1 --ipsecpolicy-id $IPSEC_POLICY_ID_1 --peer-id  $VPN_SERVICE_V4_IP_2 --peer-address  $VPN_SERVICE_V4_IP_2 --psk $VPN_PSK --peer-cidr $SUBNET_IP_PREFIX$NUM_2.0/24 --name cf-ipsec-site-connection-$NUM_1
neutron ipsec-site-connection-create --vpnservice-id $VPN_SERVICE_ID_1 --ikepolicy-id $IKE_POLICY_ID_1 --ipsecpolicy-id $IPSEC_POLICY_ID_1 --peer-id  $VPN_SERVICE_V4_IP_2 --peer-address  $VPN_SERVICE_V4_IP_2 --psk $VPN_PSK --peer-cidr $SUBNET_IP_PREFIX$NUM_2.0/24 --name cf-ipsec-site-connection-$NUM_1

echo neutron ipsec-site-connection-create --vpnservice-id $VPN_SERVICE_ID_2 --ikepolicy-id $IKE_POLICY_ID_2 --ipsecpolicy-id $IPSEC_POLICY_ID_2 --peer-id  $VPN_SERVICE_V4_IP_1 --peer-address  $VPN_SERVICE_V4_IP_1 --psk $VPN_PSK --peer-cidr $SUBNET_IP_PREFIX$NUM_1.0/24 --name cf-ipsec-site-connection-$NUM_2
neutron ipsec-site-connection-create --vpnservice-id $VPN_SERVICE_ID_2 --ikepolicy-id $IKE_POLICY_ID_2 --ipsecpolicy-id $IPSEC_POLICY_ID_2 --peer-id  $VPN_SERVICE_V4_IP_1 --peer-address  $VPN_SERVICE_V4_IP_1 --psk $VPN_PSK --peer-cidr $SUBNET_IP_PREFIX$NUM_1.0/24 --name cf-ipsec-site-connection-$NUM_2
neutron ipsec-site-connection-list
#neutron ipsec-site-connection-delete cf-ipsec-site-connection-$NUM_1
#neutron ipsec-site-connection-delete cf-ipsec-site-connection-$NUM_2

