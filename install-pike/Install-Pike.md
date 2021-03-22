[toc]
# openstack部署1+1 
## 搭建本地yum源

### 下载rpm包的shell脚本

```shell
tee down-rpms.sh << EOF
#!/bin/bash
RPMS_FILE=rpms.txt
COMMON_RPMS_FILE=common-rpms.txt
RES_RPMS_FILE=res-rpms.txt
RES_COMMON_RPMS_FILE=res-common-rpms.txt
URL=http://vault.centos.org/7.5.1804/cloud/x86_64/openstack-pike
COMMON_DIR=common
URL_COMMON="$URL/$COMMON_DIR"

function create_dir() {
  if [ ! -d "$1" ]; then
    mkdir "$1"
  fi
}

function gen_args_rpms_2_file() {
  if [ -n "$1" ] && [ -n "$2" ]; then
    cat "$1" | grep ".rpm" | awk '{print $3}' > "$2"
  fi
}

function gen_rpms_2_files() {
  gen_args_rpms_2_file $RPMS_FILE $RES_RPMS_FILE 
  gen_args_rpms_2_file $COMMON_RPMS_FILE $RES_COMMON_RPMS_FILE 
}

function wget_args_files() {
  if [ -n "$1" ] && [ -n "$2" ]; then
    for file in `cat $2`; do
      if [ -d "$3" ]; then
        if [ ! -f "$3/$file" ]; then
          echo wget -b  -P "$3" "$1/$file" 
          wget -b  -P "$3" "$1/$file" 
        fi
      else 
        if [ ! -f "$file" ]; then
          echo wget -b "$1/$file" 
          wget -b "$1/$file" 
        fi
      fi
    done
  fi
}

function down_all_rpms_files() {
  wget_args_files "$URL" "$RES_RPMS_FILE" 
  create_dir $COMMON_DIR
  wget_args_files "$URL_COMMON" "$RES_COMMON_RPMS_FILE" "$COMMON_DIR"
}

function main() {
  gen_rpms_2_files
  down_all_rpms_files
}

main

EOF
```

### 下载pike的rpm包

```shell
chmod a+x ./down-rpms.sh && ./down-rpms.sh
```
### 配置本地的yum源

#### 安装配置和发布源的软件
```shell
yum -y install httpd createrepo
```

#### 配置yum源文件和文件权限

```shell
mkdir -p /var/www/html/
cp -r /root/openstack/pike /var/www/html/

cd /var/www/html/pike/rpms7.5
rm –rf repodata
createrepo .

#5.给文件夹添加权限。（注：确保pike目录及其所有父目录（直到根目录）有rx权限）
#如果需要，可以使用类似如下的命令组合。
chmod -R a+rx /var/www/html/pike	# 有–R
chmod a+rx /var/www/html			# 以下都没有-R
chmod a+rx /var/www
chmod a+rx /var
chmod a+rx /
```

#### 配置yum repo文件
```shell
tee /etc/yum.repos.d/pike-75.repo << EOF
[pike-75]
name=pike-75
baseurl=http://192.168.8.200/pike/rpms7.5
enabled=1
gpgcheck=0
EOF

# 配置nova依赖的kvm的源
tee /etc/yum.repos.d/CentOS-kvm.repo << EOF
[Virt]
name=CentOS- - Base
#mirrorlist=http://mirrorlist.centos.org/?release=&arch=&repo=os&infra=
baseurl=http://mirrors.sohu.com/centos/7/virt/x86_64/kvm-common/
#baseurl=http://mirror.centos.org/centos//os//
gpgcheck=0
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7
EOF

```

### 发布源
```shell
systemctl enable httpd.service
systemctl restart httpd.service
```

### 配置防火墙策略
```shell
#iptables -t filter -A INPUT -p tcp --dport 80 -j ACCEPT
#iptables -t filter -A OUTPUT -p tcp --sport 80 -j ACCEPT
#iptables -t filter -A INPUT -p udp --dport 80 -j ACCEPT
#iptables -t filter -A OUTPUT -p udp --sport 80 -j ACCEPT

#systemctl restart firewalld

# 开放端口
firewall-cmd --permanent --add-port=80/tcp
firewall-cmd --permanent --add-port=5672/tcp
firewall-cmd --permanent --add-port=8778/tcp
firewall-cmd --permanent --add-port=9696/tcp
firewall-cmd --permanent --add-port=9292/tcp
firewall-cmd --permanent --add-port=15672/tcp
#firewall-cmd --permanent --add-port=80/udp

# 移除端口
#firewall-cmd --permanent --remove-port=80/tcp
#firewall-cmd --permanent --remove-port=80/udp

# 重启防火墙
firewall-cmd --reload


# 查询端口是否开放
firewall-cmd --query-port=80/tcp
firewall-cmd --query-port=5672/tcp
firewall-cmd --query-port=8778/tcp
firewall-cmd --query-port=9696/tcp
firewall-cmd --query-port=9292/tcp
firewall-cmd --query-port=15672/tcp
#firewall-cmd --query-port=80/udp
```

### 验证源

```shell
打开浏览器分别输入如下URL进行测试，出现如下内容则配置成功
http://192.168.8.200/pike/rpms7.5/
注：IP地址修改为安装了HTTPD服务的IP
验证可以执行下载安装了
echo N | yum install openstack-keystone 
```

## 安装部署
### 配置dns解析(所有机器)
```shell
tee /etc/resolv.conf << EOF
nameserver 114.114.114.114
nameserver 8.8.8.8 
EOF

```

### 更新所有机器
在所有机器上执行更新操作 升级系统
```shell
yum -y update
```

### 设置网络

#### 设置控制节点网络

```shell
ETH0=ens35
IP=16.16.16.1
IP_MASK=255.255.255.0
tee /etc/sysconfig/network-scripts/ifcfg-$ETH0 << EOF
TYPE=Ethernet
PROXY_METHOD=none
BROWSER_ONLY=no
BOOTPROTO=static
DEFROUTE=yes
IPV4_FAILURE_FATAL=no
IPV6INIT=yes
IPV6_AUTOCONF=yes
IPV6_DEFROUTE=yes
IPV6_FAILURE_FATAL=no
IPV6_ADDR_GEN_MODE=stable-privacy
NAME=$ETH0
DEVICE=$ETH0
ONBOOT=yes
IPADDR=$IP
NETMASK=$IP_MASK
EOF

```

#### 设置计算节点网络

```shell
ETH0=ens35
IP=16.16.16.2
IP_MASK=255.255.255.0
tee /etc/sysconfig/network-scripts/ifcfg-$ETH0 << EOF
TYPE=Ethernet
PROXY_METHOD=none
BROWSER_ONLY=no
BOOTPROTO=static
DEFROUTE=yes
IPV4_FAILURE_FATAL=no
IPV6INIT=yes
IPV6_AUTOCONF=yes
IPV6_DEFROUTE=yes
IPV6_FAILURE_FATAL=no
IPV6_ADDR_GEN_MODE=stable-privacy
NAME=$ETH0
DEVICE=$ETH0
ONBOOT=yes
IPADDR=$IP
NETMASK=$IP_MASK
EOF

```



#### 重启网络服务(所有节点)

```shell
systemctl restart network
```

### 配置/etc/hosts(所有节点)
```shell
tee /etc/hosts << EOF
127.0.0.1   localhost localhost.localdomain localhost4 localhost4.localdomain4
::1         localhost localhost.localdomain localhost6 localhost6.localdomain6
192.168.8.201 controller-0
192.168.8.202 compute-0
EOF

```

### 关闭NetworkManager服务(所有节点)

* 关闭NetworkManager是为了防止重启自动修改/etc/resolv.conf文件

```shell
systemctl enable NetworkManager
systemctl stop NetworkManager 
systemctl status NetworkManager 
systemctl disable NetworkManager 
```

### 配置下载源的yum repo文件(所有节点)
```shell
tee /etc/yum.repos.d/pike-75.repo << EOF
[pike-75]
name=pike-75
baseurl=http://192.168.8.200/pike/rpms7.5
enabled=1
gpgcheck=0
EOF

# 配置nova依赖的kvm的源
tee /etc/yum.repos.d/CentOS-kvm.repo << EOF
[Virt]
name=CentOS- - Base
#mirrorlist=http://mirrorlist.centos.org/?release=&arch=&repo=os&infra=
baseurl=http://mirrors.sohu.com/centos/7/virt/x86_64/kvm-common/
#baseurl=http://mirror.centos.org/centos//os//
gpgcheck=0
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7
EOF

```

### openstack基本包安装(所有节点)
```shell
yum install -y openstack-utils openstack-selinux python-openstackclient
```

### 关闭 set SELINUX disabled(所有节点)
```shell
/usr/sbin/setenforce 0

VALUE="disabled"; FILE=/etc/sysconfig/selinux; KEY="SELINUX"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "^$KEY" -w -n -m1 $FILE | awk '{if (NR==1) print$0}' | awk -F ':' '{print$1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```

### 安装ntp(所有节点)
```shell
yum install -y chrony
```
#### 配置ntp/etc/chrony.conf
* /etc/chrony.conf

##### 所有节点执行的ntp配置

* allow

```shell
VALUE="192.168.0.0/16"; FILE=/etc/chrony.conf; KEY="allow"; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk '{if (NR==1) print$0}' | awk -F ':' '{print$1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

```

##### 计算节点执行的ntp配置

* server

```shell
# 删除多余的server

VALUE="controller-0"; FILE=/etc/chrony.conf; KEY="server"; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m2 $FILE | awk '{if (NR==2) print$0}' | awk -F ':' '{print$1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}d" $FILE;fi

VALUE="controller-0"; FILE=/etc/chrony.conf; KEY="server"; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m2 $FILE | awk '{if (NR==2) print$0}' | awk -F ':' '{print$1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}d" $FILE;fi

VALUE="controller-0"; FILE=/etc/chrony.conf; KEY="server"; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m2 $FILE | awk '{if (NR==2) print$0}' | awk -F ':' '{print$1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}d" $FILE;fi

# 替换server
VALUE="controller-0"; FILE=/etc/chrony.conf; KEY="server"; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk '{if (NR==1) print$0}' | awk -F ':' '{print$1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```

#### 重启ntp的chrony服务
```shell
systemctl enable chronyd.service
systemctl restart chronyd.service
```

#### 验证ntp
```shell
chronyc sources
```
##### 控制节点ntp验证

```shell
[root@localhost ~]# chronyc sources
210 Number of sources = 4
MS Name/IP address         Stratum Poll Reach LastRx Last sample               
===============================================================================
^* 119.28.206.193                2   6    17    22  +7950us[ +511us] +/-   65ms
^- ntp6.flashdance.cx            2   6    17    22    -29ms[  -29ms] +/-  208ms
^+ ntp5.flashdance.cx            2   6    17    23    -25ms[  -32ms] +/-  166ms
^- tick.ntp.infomaniak.ch        1   6    17    21  +4448us[+4448us] +/-  109ms
```


##### 计算节点ntp验证

```shell
[root@localhost ~]# chronyc sources
210 Number of sources = 1
MS Name/IP address         Stratum Poll Reach LastRx Last sample               
===============================================================================
^? controller-0                  0   6     0     -     +0ns[   +0ns] +/-    0ns
```

### 安装MySQL(控制节点)
#### 安装MySQL
```shell

#yum install -y mysql-server python-mysqldb

yum install -y mariadb-server

systemctl  start mariadb
systemctl status mariadb
systemctl enable mariadb    
mysql_secure_installation
```

#### 配置mysql
#### 启动和设置开启自启动mysql
```shell
# 启动mysql
systemctl  start mariadb
# 检查mysql状态
systemctl status mariadb
# 设置为开机启动服务
systemctl enable mariadb
```

#### 配置mysql的选项
```shell
# 配置mysql
mysql_secure_installation
```
```shell
[root@localhost network-scripts]# mysql_secure_installation 

NOTE: RUNNING ALL PARTS OF THIS SCRIPT IS RECOMMENDED FOR ALL MariaDB
      SERVERS IN PRODUCTION USE!  PLEASE READ EACH STEP CAREFULLY!

In order to log into MariaDB to secure it, we'll need the current
password for the root user.  If you've just installed MariaDB, and
you haven't set the root password yet, the password will be blank,
so you should just press enter here.

Enter current password for root (enter for none): 
OK, successfully used password, moving on...

Setting the root password ensures that nobody can log into the MariaDB
root user without the proper authorisation.

Set root password? [Y/n] y
New password: 
Re-enter new password: 
Password updated successfully!
Reloading privilege tables..
 ... Success!


By default, a MariaDB installation has an anonymous user, allowing anyone
to log into MariaDB without having to have a user account created for
them.  This is intended only for testing, and to make the installation
go a bit smoother.  You should remove them before moving into a
production environment.

Remove anonymous users? [Y/n] y
 ... Success!

Normally, root should only be allowed to connect from 'localhost'.  This
ensures that someone cannot guess at the root password from the network.

Disallow root login remotely? [Y/n] n
 ... skipping.

By default, MariaDB comes with a database named 'test' that anyone can
access.  This is also intended only for testing, and should be removed
before moving into a production environment.

Remove test database and access to it? [Y/n] n
 ... skipping.

Reloading the privilege tables will ensure that all changes made so far
will take effect immediately.

Reload privilege tables now? [Y/n] y
 ... Success!

Cleaning up...

All done!  If you've completed all of the above steps, your MariaDB
installation should now be secure.

Thanks for using MariaDB!
```

#### 配置/etc/my.cnf文件

* mysql字符集为utf-8

* /etc/my.cnf 文件在  [mysqld]  标签下添加

  init_connect='SET collation_connection = utf8_unicode_ci'
  init_connect='SET NAMES utf8'
  character-set-server=utf8
  collation-server=utf8_unicode_ci
  skip-character-set-client-handshake

  max_connections=4096

  
```shell
VALUE="init_connect='SET collation_connection = utf8_unicode_ci'\ninit_connect='SET NAMES utf8'\ncharacter-set-server=utf8\ncollation-server=utf8_unicode_ci\nskip-character-set-client-handshake\nmax_connections=4096"; FILE=/etc/my.cnf; KEY="\[mysqld\]"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE ;if [ -n "$LINE" ]; then sed -i "${LINE}s/.*/$KEY\n$VALUE/" $FILE; else echo -e "$KEY\n$VALUE" >> $FILE; fi
```

* /etc/my.cnf.d/client.cnf 文件
在  [client]  标签下添加default-character-set=utf8
```shell
VALUE="default-character-set=utf8"; FILE=/etc/my.cnf.d/client.cnf; KEY="\[client\]"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE ;if [ -n "$LINE" ]; then sed -i "${LINE}s/.*/$KEY\n$VALUE/" $FILE; else echo "$KEY\n$VALUE" >> $FILE; fi
```


* /etc/my.cnf.d/mysql-clients.cnf  文件
在  [mysql]  标签下添加default-character-set=utf8

```shell
VALUE="default-character-set=utf8"; FILE=/etc/my.cnf.d/mysql-clients.cnf; KEY="\[mysql\]"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE ;if [ -n "$LINE" ]; then sed -i "${LINE}s/.*/$KEY\n$VALUE/" $FILE; else echo "$KEY\n$VALUE" >> $FILE; fi
```



#### 配置mysql最大文件描述符限制

* /usr/lib/systemd/system/mariadb.service

  解决mysql 最大连接数 214 问题

  在文件[Service]下添加:

  LimitNOFILE=65535
  LimitNPROC=65535

```shell
KEY="\[Service\]"; VALUE="LimitNOFILE=65535\nLimitNPROC=65535"; NEW_VALUE="$KEY\n$VALUE" FILE=/usr/lib/systemd/system/mariadb.service; LINE=$(grep "^$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE ;if [ -n "$LINE" ]; then sed -i "${LINE}s/.*/$NEW_VALUE/" $FILE; else echo -e "$KEY\n$VALUE" >> $FILE; fi
```



#### 重启mysql服务

```shell
systemctl daemon-reload
systemctl restart  mariadb.service
```

#### 查看mysql修改验证
```shell
#查看mysql字符集
mysql -uroot -proot -e "show variables like '%character%';show variables like '%collation%'";

# 查看mysql最大连接数
mysql -uroot -proot -e "show variables like 'max_connections';";

```
```shell
[root@localhost network-scripts]# mysql -uroot -proot -e "show variables like '%character%';show variables like '%collation%'";
+--------------------------+----------------------------+
| Variable_name            | Value                      |
+--------------------------+----------------------------+
| character_set_client     | utf8                       |
| character_set_connection | utf8                       |
| character_set_database   | utf8                       |
| character_set_filesystem | binary                     |
| character_set_results    | utf8                       |
| character_set_server     | utf8                       |
| character_set_system     | utf8                       |
| character_sets_dir       | /usr/share/mysql/charsets/ |
+--------------------------+----------------------------+
+----------------------+-----------------+
| Variable_name        | Value           |
+----------------------+-----------------+
| collation_connection | utf8_unicode_ci |
| collation_database   | utf8_unicode_ci |
| collation_server     | utf8_unicode_ci |
+----------------------+-----------------+

[root@controller-0 ~]# mysql -uroot -proot -e "show variables like 'max_connections';";
+-----------------+-------+
| Variable_name   | Value |
+-----------------+-------+
| max_connections | 4096  |
+-----------------+-------+

```

#### 放通3306端口
```shell
firewall-cmd --zone=public --add-port=3306/tcp --permanent  # 开启3306端口
firewall-cmd --reload  # 重启防火墙
firewall-cmd --query-port=3306/tcp  # 查看3306端口是否开启
```
```shell
[root@localhost network-scripts]# firewall-cmd --zone=public --add-port=3306/tcp --permanent  # 开启3306端口
success
[root@localhost network-scripts]# firewall-cmd --reload  # 重启防火墙
success
[root@localhost network-scripts]# firewall-cmd --query-port=3306/tcp  # 查看3306端口是否开启
yes

```

#### mysql赋权
```shell
mysql -uroot -proot -e "grant all on root.* to 'root'@'%' identified by 'root';";
mysql -uroot -proot -e "grant all on root.* to 'root'@'172.29.6.34' identified by 'root';";

```
#### 查看远程连接的权限
```shell
mysql -uroot -proot -h192.168.8.201 -e "show databases;";
```

### 安装RabbitMQ(控制节点)
```shell
 install -y rabbitmq-server
```

#### 启动RabbitMQ
```shell
systemctl status rabbitmq-server # 启动
systemctl enable rabbitmq-server # 开机自启动
```

#### 添加rabbitmq用户并配置权限
```shell
rabbitmqctl add_user openstack openstack123
rabbitmqctl set_permissions openstack ".*" ".*" ".*"
```
```shell
[root@controller-0 ~]# rabbitmqctl set_permissions openstack ".*" ".*" ".*"
Setting permissions for user "openstack" in vhost "/" ...
```

### 安装Memcached（控制节点）
```shell
yum install -y memcached python-memcached
```

#### 配置Memcached
```shell
VALUE="\"-l 127.0.0.1,::1,controller-0\""; FILE=/etc/sysconfig/memcached; KEY="OPTIONS"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```

#### 启动Memcached服务
```shell
systemctl enable memcached.service
systemctl restart memcached.service
```


### 安装其他软件
```shell
 yum install -y vlan bridge-utils
```



### 安装keystone

```shell

yum install -y openstack-keystone httpd mod_wsgi
```

#### 创建keyston的库
```shell
mysql -uroot -proot -e "CREATE DATABASE keystone;"; 
mysql -uroot -proot -e "GRANT ALL PRIVILEGES ON keystone.* TO 'keystone'@'localhost' IDENTIFIED BY 'KEYSTONE_DBPASS';"; 
mysql -uroot -proot -e "GRANT ALL ON keystone.* TO 'keystone'@'%' IDENTIFIED BY 'keystone';"; 
```

#### 设置keyston的/etc/keystone/keystone.conf

* mysql
```shell
VALUE="mysql+pymysql://keystone:keystone@controller-0/keystone"; FILE=/etc/keystone/keystone.conf; KEY="connection ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```

* In the [token] section, configure the Fernet token provider:
```shell
VALUE="fernet"; FILE=/etc/keystone/keystone.conf; KEY="provider ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m2 $FILE | awk '{if (NR==2) print$0}' | awk -F ':' '{print$1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi


# admin_token
ADMIN_TOKEN=$(openssl rand -hex 10);
echo $ADMIN_TOKEN;
openstack-config --set /etc/keystone/keystone.conf DEFAULT admin_token $ADMIN_TOKEN

```

#### 加载Keystone数据库的schema
```shell
su -s /bin/sh -c "keystone-manage db_sync" keystone
```

#### 创建证书和密钥
```shell

keystone-manage fernet_setup --keystone-user keystone --keystone-group keystone
keystone-manage credential_setup --keystone-user keystone --keystone-group keystone
```

#### 启动 keystone服务
```shell

 keystone-manage bootstrap --bootstrap-password Fiberhome.2020 \
  --bootstrap-admin-url http://controller-0:35357/v3/ \
  --bootstrap-internal-url http://controller-0:5000/v3/ \
  --bootstrap-public-url http://controller-0:5000/v3/ \
  --bootstrap-region-id RegionOne
 
```

#### 配置Http Server
* ServerName controller-0
```shell
VALUE="controller-0"; FILE=/etc/httpd/conf/httpd.conf; KEY="ServerName"; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m2 $FILE | awk '{if(NR==2){print $0}}' |awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```


#### 创建软连接
* /usr/share/keystone/wsgi-keystone.conf
```shell
ln -s /usr/share/keystone/wsgi-keystone.conf /etc/httpd/conf.d/

```

#### 启动htttp服务
```shell
systemctl enable httpd.service
systemctl restart httpd.service
```
#### 启动keystone服务



```shell
ln -s /usr/lib/systemd/system/httpd.service /etc/systemd/system/openstack-keystone.service
systemctl daemon-reload
systemctl restart openstack-keystone
```
#### 设置环境变量
```shell

export OS_USERNAME=admin
export OS_PASSWORD=Fiberhome.2020
export OS_PROJECT_NAME=admin
export OS_USER_DOMAIN_NAME=Default
export OS_PROJECT_DOMAIN_NAME=Default
export OS_AUTH_URL=http://controller-0:35357/v3
export OS_IDENTITY_API_VERSION=3

```



#### 创建Demo用户信息
```shell
export OS_USERNAME=admin
export OS_PASSWORD= Fiberhome.2020
export OS_PROJECT_NAME=admin
export OS_USER_DOMAIN_NAME=Default
export OS_PROJECT_DOMAIN_NAME=Default
export OS_AUTH_URL=http://controller-0:35357/v3
export OS_IDENTITY_API_VERSION=3

unset OS_TOKEN

openstack project create --domain default --description "Service Project" service
openstack project create --domain default --description "Demo Project" demo
openstack user create --domain default --password-prompt demo
openstack role create user 
openstack role add --project demo --user demo user
```
```shell
[root@controller-0 ~]# openstack project create --domain default --description "Service Project" service
+-------------+----------------------------------+
| Field       | Value                            |
+-------------+----------------------------------+
| description | Service Project                  |
| domain_id   | default                          |
| enabled     | True                             |
| id          | e729c87c9a1a4705b6298a2519bf7aa6 |
| is_domain   | False                            |
| name        | service                          |
| parent_id   | default                          |
+-------------+----------------------------------+
[root@controller-0 ~]# openstack project create --domain default --description "Demo Project" demo
+-------------+----------------------------------+
| Field       | Value                            |
+-------------+----------------------------------+
| description | Demo Project                     |
| domain_id   | default                          |
| enabled     | True                             |
| id          | f6fe0ea2b3534bffa37d7334feeedce2 |
| is_domain   | False                            |
| name        | demo                             |
| parent_id   | default                          |
+-------------+----------------------------------+
[root@controller-0 ~]# openstack user create --domain default --password-prompt demo
User Password:
Repeat User Password:
+---------------------+----------------------------------+
| Field               | Value                            |
+---------------------+----------------------------------+
| domain_id           | default                          |
| enabled             | True                             |
| id                  | 62fa53eb8b6d467a8f84991dac8812b3 |
| name                | demo                             |
| options             | {}                               |
| password_expires_at | None                             |
+---------------------+----------------------------------+


[root@controller-0 ~]# openstack role create user
+-----------+----------------------------------+
| Field     | Value                            |
+-----------+----------------------------------+
| domain_id | None                             |
| id        | 4e2da1309b1a4d21b7e5af390aed8f21 |
| name      | user                             |
+-----------+----------------------------------+
[root@controller-0 ~]# openstack role add --project demo --user demo user
```

```shell
tee /root/admin-openrc.sh << EOF
export OS_PROJECT_DOMAIN_NAME=Default
export OS_USER_DOMAIN_NAME=Default
export OS_PROJECT_NAME=admin
export OS_USERNAME=admin
export OS_PASSWORD=Fiberhome.2020
export OS_AUTH_URL=http://controller-0:35357/v3
export OS_IDENTITY_API_VERSION=3
export OS_IMAGE_API_VERSION=2
EOF

```
```shell
[root@controller-0 ~]# source admin-openrc.sh 
[root@controller-0 ~]# openstack token issue
+------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Field      | Value                                                                                                                                                                                   |
+------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| expires    | 2020-08-10T09:08:50+0000                                                                                                                                                                |
| id         | gAAAAABfMQCScOzZ2WWeeDgbpL_uSt2GMZAnf1FUhgfYe3I11Ohx1zE883u8XG3T6Yd2bfjdE5ZrQRZ2h4o9H5NlmJHzwECDxCt--E-IjUoJa_m4DubaUY8zD30hmqWCcbJEbByoLcnzIqFHBPhdfFIEv2hRIHle3_4mXtTG37ZYSe3S2YKiNYk |
| project_id | f70a8b7d3aa047bc8a278a401186500a                                                                                                                                                        |
| user_id    | 277972b4f2284fa386f6475babfbda9a                                                                                                                                                        |
+------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
```

#### 验证keystone是否成功
* Unset the temporary OS_AUTH_URL and OS_PASSWORD environment variable:
```shell
unset OS_AUTH_URL OS_PASSWORD
```

* As the admin user, request an authentication token:
```shell
openstack --os-auth-url http://controller-0:35357/v3 \
  --os-project-domain-name Default --os-user-domain-name Default \
  --os-project-name admin --os-username admin token issue
  
```
  ```shell
[root@controller-0 ~]# openstack --os-auth-url http://controller-0:35357/v3 \
>   --os-project-domain-name Default --os-user-domain-name Default \
>   --os-project-name admin --os-username admin token issue


+------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Field      | Value                                                                                                                                                                                   |
+------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| expires    | 2020-08-10T10:11:14+0000                                                                                                                                                                |
| id         | gAAAAABfMQ8yEPEYCuEH06CHfBFlnyMRx0gnkxUjEOPrLov59FmLlu0a9LtdKnW9X7LResb1_bcy23Mv5Ost6EvcQABgHwue6_6vgLch1fzhMYy5Miysli0Ezrrsrfp4d7uTETxQc8nChgA5vxLwwsX1DHwauvk-Tz_IVktuBDCpkcOaG_2V0cY |
| project_id | f70a8b7d3aa047bc8a278a401186500a                                                                                                                                                        |
| user_id    | 277972b4f2284fa386f6475babfbda9a                                                                                                                                                        |
+------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

  ```

* As the demo user, request an authentication token:
```shell

openstack --os-auth-url http://controller-0:5000/v3 \
  --os-project-domain-name Default --os-user-domain-name Default \
  --os-project-name demo --os-username demo token issue
  
```
```shell
[root@controller-0 ~]# openstack --os-auth-url http://controller-0:5000/v3 \
>   --os-project-domain-name Default --os-user-domain-name Default \
>   --os-project-name demo --os-username demo token issue


+------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Field      | Value                                                                                                                                                                                   |
+------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| expires    | 2020-08-10T10:12:29+0000                                                                                                                                                                |
| id         | gAAAAABfMQ99nUZ5CPPKqfS7ht_GNxcGGilIkEHWS9eThKUvaIYLZEY63HevwHrdo01rrKNPICqptsph7P3yHSLZ4ndaTt1tDrVVpYTk_yF91QsDtwkPFv1qR-IRNLPASjjcEbJg1sYqA9DtVQYnIQwGhx4aMudSpoWhT5GAYY9TFBtubsesvXE |
| project_id | f6fe0ea2b3534bffa37d7334feeedce2                                                                                                                                                        |
| user_id    | 62fa53eb8b6d467a8f84991dac8812b3                                                                                                                                                        |
+------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

```

#### create admin-openrc file
```shell
tee /root/admin-openrc.sh << EOF
export OS_PROJECT_DOMAIN_NAME=Default
export OS_USER_DOMAIN_NAME=Default
export OS_PROJECT_NAME=admin
export OS_USERNAME=admin
export OS_PASSWORD=Fiberhome.2020
export OS_AUTH_URL=http://controller-0:35357/v3
export OS_IDENTITY_API_VERSION=3
export OS_IMAGE_API_VERSION=2
EOF

```

#### create demo-openrc file
```shell
tee /root/demo-openrc.sh << EOF
export OS_PROJECT_DOMAIN_NAME=Default
export OS_USER_DOMAIN_NAME=Default
export OS_PROJECT_NAME=demo
export OS_USERNAME=demo
export OS_PASSWORD=Fiberhome.2020
export OS_AUTH_URL=http://controller-0:35357/v3
export OS_IDENTITY_API_VERSION=3
export OS_IMAGE_API_VERSION=2
EOF

```
##### 验证demo用户的获取token
```shell
[root@controller-0 ~]# . demo-openrc.sh 
[root@controller-0 ~]# openstack token issue
+------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Field      | Value                                                                                                                                                                                   |
+------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| expires    | 2020-08-10T10:18:45+0000                                                                                                                                                                |
| id         | gAAAAABfMRD1Kg4qlo5OkSdy4UjcTQoQ0l1aRDi-vZycBqpkE1o9RVU43xxYO0ygh2rJHJ5cO21Iw3c7a6URyo4G19bgRJyTv0_jj7qU2SDH7VTMcQZFu0NEOufeu4PrUxkC2Mp3Gb9-UtV8Sks6M5PaMP6pStBtJbwBNKFGUoPNdGH9Z4c2XcU |
| project_id | f6fe0ea2b3534bffa37d7334feeedce2                                                                                                                                                        |
| user_id    | 62fa53eb8b6d467a8f84991dac8812b3                                                                                                                                                        |
+------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
```


### 安装Glance

#### 创建glance的库
```shell
mysql -uroot -proot -e "CREATE DATABASE glance;"; 
mysql -uroot -proot -e "GRANT ALL ON glance.* TO 'glance'@'localhost' IDENTIFIED BY 'glance';";
mysql -uroot -proot -e "GRANT ALL ON glance.* TO 'glance'@'%' IDENTIFIED BY 'glance';"; 
```

#### 创建glance用户,并添加管理员角色
```shell
openstack user create --domain default --password-prompt glance
openstack role add --project service --user glance admin
```
```shell
[root@controller-0 ~]# openstack user create --domain default --password-prompt glance
User Password:
Repeat User Password:
+---------------------+----------------------------------+
| Field               | Value                            |
+---------------------+----------------------------------+
| domain_id           | default                          |
| enabled             | True                             |
| id                  | 9af4bc77169a48498b4d603ac7c13b65 |
| name                | glance                           |
| options             | {}                               |
| password_expires_at | None                             |
+---------------------+----------------------------------+
```

#### 在keystone创建glance服务和endpoint
```shell
openstack service create --name glance  --description "OpenStack Image" image

openstack endpoint create --region RegionOne   image public http://controller-0:9292

openstack endpoint create --region RegionOne  image internal http://controller-0:9292

openstack endpoint create --region RegionOne  image admin http://controller-0:9292
```
```shell
[root@controller-0 ~]# openstack service create --name glance  --description "OpenStack Image" image
+-------------+----------------------------------+
| Field       | Value                            |
+-------------+----------------------------------+
| description | OpenStack Image                  |
| enabled     | True                             |
| id          | ec5f1c86f0dd43cd97c57994429fe870 |
| name        | glance                           |
| type        | image                            |
+-------------+----------------------------------+
[root@controller-0 ~]# openstack endpoint create --region RegionOne   image public http://controller-0:9292
+--------------+----------------------------------+
| Field        | Value                            |
+--------------+----------------------------------+
| enabled      | True                             |
| id           | 8365b9b1f5b845f48d119ee974fb4f8c |
| interface    | public                           |
| region       | RegionOne                        |
| region_id    | RegionOne                        |
| service_id   | ec5f1c86f0dd43cd97c57994429fe870 |
| service_name | glance                           |
| service_type | image                            |
| url          | http://controller-0:9292         |
+--------------+----------------------------------+
[root@controller-0 ~]# 
[root@controller-0 ~]# openstack endpoint create --region RegionOne  image internal http://controller-0:9292
+--------------+----------------------------------+
| Field        | Value                            |
+--------------+----------------------------------+
| enabled      | True                             |
| id           | 0d2992a0d5f24fb5983469d47fb1714a |
| interface    | internal                         |
| region       | RegionOne                        |
| region_id    | RegionOne                        |
| service_id   | ec5f1c86f0dd43cd97c57994429fe870 |
| service_name | glance                           |
| service_type | image                            |
| url          | http://controller-0:9292         |
+--------------+----------------------------------+
[root@controller-0 ~]# 
[root@controller-0 ~]# openstack endpoint create --region RegionOne  image admin http://controller-0:9292
+--------------+----------------------------------+
| Field        | Value                            |
+--------------+----------------------------------+
| enabled      | True                             |
| id           | 43ba966bd8bf4b1b9f5f4361925f1526 |
| interface    | admin                            |
| region       | RegionOne                        |
| region_id    | RegionOne                        |
| service_id   | ec5f1c86f0dd43cd97c57994429fe870 |
| service_name | glance                           |
| service_type | image                            |
| url          | http://controller-0:9292         |
+--------------+----------------------------------+

```


#### yum安装glance rpm包
```shell
yum install -y openstack-glance

```

####  修改Glance配置文件/etc/glance/glance-api.conf
```shell
# connection
VALUE="mysql+pymysql://glance:glance@controller-0/glance"; FILE=/etc/glance/glance-api.conf; KEY="connection ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# keystone_authtoken
VALUE="auth_uri = http://controller-0:5000\nauth_url = http://controller-0:35357\nmemcached_servers = controller-0:11211\nauth_type = password\nproject_domain_name = default\nuser_domain_name = default\nproject_name = service\nusername = glance\npassword = glance"; FILE=/etc/glance/glance-api.conf; KEY="\[keystone_authtoken\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi


# glance_store
VALUE="stores = file,http\ndefault_store = file\nfilesystem_store_datadir = /var/lib/glance/images/"; FILE=/etc/glance/glance-api.conf; KEY="\[glance_store\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# paste_deploy
VALUE="flavor = keystone"; FILE=/etc/glance/glance-api.conf; KEY="\[paste_deploy\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```

####  修改Glance配置文件glance-registry.conf
```shell
# connection
VALUE="mysql+pymysql://glance:glance@controller-0/glance"; FILE=/etc/glance/glance-registry.conf; KEY="connection ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# keystone_authtoken
VALUE="auth_uri = http://controller-0:5000\nauth_url = http://controller-0:35357\nmemcached_servers = controller-0:11211\nauth_type = password\nproject_domain_name = default\nuser_domain_name = default\nproject_name = service\nusername = glance\npassword = glance"; FILE=/etc/glance/glance-registry.conf; KEY="\[keystone_authtoken\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# paste_deploy
VALUE="flavor = keystone"; FILE=/etc/glance/glance-registry.conf; KEY="\[paste_deploy\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```

#### 生成glance 数据库
```shell
su -s /bin/sh -c "glance-manage db_sync" glance
```

#### 启动glance服务
```shell
systemctl enable openstack-glance-api.service
systemctl enable openstack-glance-registry.service
systemctl restart openstack-glance-api.service
systemctl restart openstack-glance-registry.service
```

#### 验证glance安装是否成功
```shell
. /root/admin-openrc.sh
mkdir /tmp/images
wget http://download.cirros-cloud.net/0.3.5/cirros-0.3.5-x86_64-disk.img -P /tmp/images/
glance image-create --name "cirros-0.3.3-x86_64" --file /tmp/images/cirros-0.3.5-x86_64-disk.img --disk-format qcow2 --container-format bare --progress
glance image-list
```
```shell
[root@controller-0 ~]# glance image-create --name "cirros-0.3.3-x86_64" --file /tmp/images/cirros-0.3.5-x86_64-disk.img --disk-format qcow2 --container-format bare --progress
[=============================>] 100%
+------------------+--------------------------------------+
| Property         | Value                                |
+------------------+--------------------------------------+
| checksum         | f8ab98ff5e73ebab884d80c9dc9c7290     |
| container_format | bare                                 |
| created_at       | 2020-08-10T10:08:20Z                 |
| disk_format      | qcow2                                |
| id               | 48196a20-df86-4ace-8aef-9b17e65c3d76 |
| min_disk         | 0                                    |
| min_ram          | 0                                    |
| name             | cirros-0.3.3-x86_64                  |
| owner            | None                                 |80

| protected        | False                                |
| size             | 13267968                             |
| status           | active                               |
| tags             | []                                   |
| updated_at       | 2020-08-10T10:08:20Z                 |
| virtual_size     | None                                 |
| visibility       | shared                               |
+------------------+--------------------------------------+
[root@controller-0 ~]# glance image-list
+--------------------------------------+---------------------+
| ID                                   | Name                |
+--------------------------------------+---------------------+
| 48196a20-df86-4ace-8aef-9b17e65c3d76 | cirros-0.3.3-x86_64 |
+--------------------------------------+---------------------+
```

### 安装Nova
#### 安装Nova-Controller节点
##### 添加nova数据库
```shell
mysql -uroot -proot -e "CREATE DATABASE nova_api;"; 
mysql -uroot -proot -e "GRANT ALL ON nova_api.* TO 'nova'@'localhost' IDENTIFIED BY 'nova';";
mysql -uroot -proot -e "GRANT ALL ON nova_api.* TO 'nova'@'%' IDENTIFIED BY 'nova';"; 

mysql -uroot -proot -e "CREATE DATABASE nova_cell0;"; 
mysql -uroot -proot -e "GRANT ALL ON nova_cell0.* TO 'nova'@'localhost' IDENTIFIED BY 'nova';";
mysql -uroot -proot -e "GRANT ALL ON nova_cell0.* TO 'nova'@'%' IDENTIFIED BY 'nova';"; 

mysql -uroot -proot -e "CREATE DATABASE nova;"; 
mysql -uroot -proot -e "GRANT ALL ON nova.* TO 'nova'@'localhost' IDENTIFIED BY 'nova';";
mysql -uroot -proot -e "GRANT ALL ON nova.* TO 'nova'@'%' IDENTIFIED BY 'nova';"; 
```

##### 设置keystone创建nova的服务和endpoint
```shell
. /root/admin-openrc.sh

openstack user create --domain default --password-prompt nova
openstack role add --project service --user nova admin

openstack service create --name nova  --description "OpenStack Compute" compute
openstack endpoint create --region RegionOne  compute public http://controller-0:8774/v2.1
openstack endpoint create --region RegionOne  compute internal http://controller-0:8774/v2.1
openstack endpoint create --region RegionOne  compute admin http://controller-0:8774/v2.1

# placement
openstack user create --domain default --password-prompt placement
openstack role add --project service --user placement admin

openstack service create --name placement  --description "Placement API" placement
openstack endpoint create --region RegionOne  placement public http://controller-0:8778
openstack endpoint create --region RegionOne  placement internal http://controller-0:8778
openstack endpoint create --region RegionOne  placement admin http://controller-0:8778
```
```shell
[root@controller-0 ~]# openstack service create --name nova  --description "OpenStack Compute" compute
+-------------+----------------------------------+
| Field       | Value                            |
+-------------+----------------------------------+
| description | OpenStack Compute                |
| enabled     | True                             |
| id          | 781b33d3945249a9b28635e4e95e0400 |
| name        | nova                             |
| type        | compute                          |
+-------------+----------------------------------+
[root@controller-0 ~]# openstack user create --domain default --password-prompt nova
# nova用户的密码
User Password:
Repeat User Password:
+---------------------+----------------------------------+
| Field               | Value                            |
+---------------------+----------------------------------+
| domain_id           | default                          |
| enabled             | True                             |
| id                  | 42c46a757a524743b16cfbe0bcb63132 |
| name                | nova                             |
| options             | {}                               |
| password_expires_at | None                             |
+---------------------+----------------------------------+
[root@controller-0 ~]# openstack role add --project service --user nova admin
[root@controller-0 ~]# openstack endpoint create --region RegionOne  compute public http://controller-0:8774/v2.1
oller-0:8774/v2.1
+--------------+----------------------------------+
| Field        | Value                            |
+--------------+----------------------------------+
| enabled      | True                             |
| id           | 070a101f37174b74bfbbac6f3ea3af38 |
| interface    | public                           |
| region       | RegionOne                        |
| region_id    | RegionOne                        |
| service_id   | 781b33d3945249a9b28635e4e95e0400 |
| service_name | nova                             |
| service_type | compute                          |
| url          | http://controller-0:8774/v2.1    |
+--------------+----------------------------------+
[root@controller-0 ~]# openstack endpoint create --region RegionOne  compute internal http://controller-0:8774/v2.1
+--------------+----------------------------------+
| Field        | Value                            |
+--------------+----------------------------------+
| enabled      | True                             |
| id           | 8c00f0d3c2154cd89831ae31e61c82bf |
| interface    | internal                         |
| region       | RegionOne                        |
| region_id    | RegionOne                        |
| service_id   | 781b33d3945249a9b28635e4e95e0400 |
| service_name | nova                             |
| service_type | compute                          |
| url          | http://controller-0:8774/v2.1    |
+--------------+----------------------------------+
[root@controller-0 ~]# openstack endpoint create --region RegionOne  compute admin http://controller-0:8774/v2.1

+--------------+----------------------------------+
| Field        | Value                            |
+--------------+----------------------------------+
| enabled      | True                             |
| id           | ee4b7b4aa4ed4383882de17bbd2944cf |
| interface    | admin                            |
| region       | RegionOne                        |
| region_id    | RegionOne                        |
| service_id   | 781b33d3945249a9b28635e4e95e0400 |
| service_name | nova                             |
| service_type | compute                          |
| url          | http://controller-0:8774/v2.1    |
+--------------+----------------------------------+


[root@controller-0 ~]# openstack user create --domain default --password-prompt placement
User Password:
Repeat User Password:
+---------------------+----------------------------------+
| Field               | Value                            |
+---------------------+----------------------------------+
| domain_id           | default                          |
| enabled             | True                             |
| id                  | da07a7de9af34775952350885db0e040 |
| name                | placement                        |
| options             | {}                               |
| password_expires_at | None                             |
+---------------------+----------------------------------+
[root@controller-0 ~]# openstack role add --project service --user placement admin
[root@controller-0 ~]# openstack service create --name placement  --description "Placement API" placement
8778
openstack endpoint create --region RegionOne  placement admin http://controller-0:8778+-------------+----------------------------------+
| Field       | Value                            |
+-------------+----------------------------------+
| description | Placement API                    |
| enabled     | True                             |
| id          | 67019c02ccee443f95403663a5c8f7eb |
| name        | placement                        |
| type        | placement                        |
+-------------+----------------------------------+
[root@controller-0 ~]# openstack endpoint create --region RegionOne  placement public http://controller-0:8778
+--------------+----------------------------------+
| Field        | Value                            |
+--------------+----------------------------------+
| enabled      | True                             |
| id           | 5d8ff6c5db084219acb8ab9b119e7355 |
| interface    | public                           |
| region       | RegionOne                        |
| region_id    | RegionOne                        |
| service_id   | 67019c02ccee443f95403663a5c8f7eb |
| service_name | placement                        |
| service_type | placement                        |
| url          | http://controller-0:8778         |
+--------------+----------------------------------+
[root@controller-0 ~]# openstack endpoint create --region RegionOne  placement internal http://controller-0:8778
+--------------+----------------------------------+
| Field        | Value                            |
+--------------+----------------------------------+
| enabled      | True                             |
| id           | b6f2661fa1bd4600808d71f30701117c |
| interface    | internal                         |
| region       | RegionOne                        |
| region_id    | RegionOne                        |
| service_id   | 67019c02ccee443f95403663a5c8f7eb |
| service_name | placement                        |
| service_type | placement                        |
| url          | http://controller-0:8778         |
+--------------+----------------------------------+
[root@controller-0 ~]# openstack endpoint create --region RegionOne  placement admin http://controller-0:8778
+--------------+----------------------------------+
| Field        | Value                            |
+--------------+----------------------------------+
| enabled      | True                             |
| id           | 85fa8b1576a24b9cb332368f680e841f |
| interface    | admin                            |
| region       | RegionOne                        |
| region_id    | RegionOne                        |
| service_id   | 67019c02ccee443f95403663a5c8f7eb |
| service_name | placement                        |
| service_type | placement                        |
| url          | http://controller-0:8778         |
+--------------+----------------------------------+

```

##### yum安装nova rpm包
```SHELL
tee /etc/yum.repos.d/CentOS-kvm.repo << EOF
[Virt]
name=CentOS-$releasever - Base
#mirrorlist=http://mirrorlist.centos.org/?release=$releasever&arch=$basearch&repo=os&infra=$infra
baseurl=http://mirrors.sohu.com/centos/7/virt/x86_64/kvm-common/
#baseurl=http://mirror.centos.org/centos/$releasever/os/$basearch/
gpgcheck=0
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7
EOF
```

```shell
yum install -y openstack-nova-api openstack-nova-conductor \
openstack-nova-console openstack-nova-novncproxy \
openstack-nova-scheduler openstack-nova-placement-api
```

##### 修改nova.conf文件
注：openstack:RABBIT_PASS替换成rabbitMQ的用户/密码
NOVA_PASS替换成nova的密码,其他密码也相应的替换。
```shell
#  In the [DEFAULT] section, enable only the compute and metadata APIs:
VALUE="osapi_compute,metadata"; FILE=/etc/nova/nova.conf; KEY="enabled_apis"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi


# In the [api_database] and [database] sections, configure database access:
# api_database
VALUE="connection = mysql+pymysql://nova:nova@controller-0/nova_api"; FILE=/etc/nova/nova.conf; KEY="\[api_database\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# database
VALUE="connection = mysql+pymysql://nova:nova@controller-0/nova"; FILE=/etc/nova/nova.conf; KEY="\[database\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# In the [DEFAULT] section, configure RabbitMQ message queue access:
VALUE="rabbit://openstack:openstack123@controller-0"; FILE=/etc/nova/nova.conf; KEY="transport_url"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# In the [api] and [keystone_authtoken] sections, configure Identity service access:
# api auth_strategy
VALUE="keystone"; FILE=/etc/nova/nova.conf; KEY="auth_strategy"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi


# keystone_authtoken
VALUE="auth_uri = http://controller-0:5000\nauth_url = http://controller-0:35357\nmemcached_servers = controller-0:11211\nauth_type = password\nproject_domain_name = default\nuser_domain_name = default\nproject_name = service\nusername = nova\npassword = nova"; FILE=/etc/nova/nova.conf; KEY="\[keystone_authtoken\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# In the [DEFAULT] section, configure the my_ip option to use the management interface IP address of the controller node:
# my_ip
VALUE="192.168.8.201"; FILE=/etc/nova/nova.conf; KEY="my_ip"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# In the [DEFAULT] section, enable support for the Networking service:
VALUE="True"; FILE=/etc/nova/nova.conf; KEY="use_neutron"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

VALUE="nova.virt.firewall.NoopFirewallDriver"; FILE=/etc/nova/nova.conf; KEY="firewall_driver"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# vnc enabled
VALUE="enabled = true"; FILE=/etc/nova/nova.conf; KEY="\[vnc\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# vncserver_listen 
VALUE="\$my_ip"; FILE=/etc/nova/nova.conf; KEY="vncserver_listen"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# vncserver_proxyclient_address
VALUE="\$my_ip"; FILE=/etc/nova/nova.conf; KEY="vncserver_proxyclient_address"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi


# In the [glance] section, configure the location of the Image service API:
# api_servers
VALUE="http://controller-0:9292"; FILE=/etc/nova/nova.conf; KEY="api_servers"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#In the [oslo_concurrency] section, configure the lock path:
VALUE="/var/lib/nova/tmp"; FILE=/etc/nova/nova.conf; KEY="lock_path"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# In the [placement] section, configure the Placement API:
VALUE="os_region_name = RegionOne\nproject_domain_name = Default\nproject_name = service\nauth_type = password\nuser_domain_name = Default\nauth_url = http://controller-0:35357/v3\nusername = placement\npassword = placement"; FILE=/etc/nova/nova.conf; KEY="\[placement\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```

##### 配置/etc/httpd/conf.d/00-nova-placement-api.conf
* Due to a packaging bug, you must enable access to the Placement API by adding the following configuration to /etc/httpd/conf.d/00-nova-placement-api.conf
```shell
KEY=Directory; FILE=/etc/httpd/conf.d/00-nova-placement-api.conf;$(grep $KEY $FILE > /dev/null); IS_IN=$?; echo $IS_IN; if [ $IS_IN -ne 0 ]; then echo "<Directory /usr/bin>
   <IfVersion >= 2.4>
      Require all granted
   </IfVersion>
   <IfVersion < 2.4>
      Order allow,deny
      Allow from all
   </IfVersion>
</Directory>" >> $FILE; fi

```
##### 重启httpd服务
```shell

systemctl restart httpd
```

##### 创建nova数据库记录
```shell
# Populate the nova-api database:
su -s /bin/sh -c "nova-manage api_db sync" nova

# Register the cell0 database:
su -s /bin/sh -c "nova-manage cell_v2 map_cell0" nova

# Create the cell1 cell:
su -s /bin/sh -c "nova-manage cell_v2 create_cell --name=cell1 --verbose" nova

# Populate the nova database:
su -s /bin/sh -c "nova-manage db sync" nova

```

##### 验证cell0 cell1正确性。
```shell
nova-manage cell_v2 list_cells
```
```shell
[root@controller-0 ~]# nova-manage cell_v2 list_cells
+-------+--------------------------------------+--------------------------------------+---------------------------------------------------+
|  Name |                 UUID                 |            Transport URL             |                Database Connection                |
+-------+--------------------------------------+--------------------------------------+---------------------------------------------------+
| cell0 | 00000000-0000-0000-0000-000000000000 |                none:/                | mysql+pymysql://nova:****@controller-0/nova_cell0 |
| cell1 | 4e86b81d-4046-40b1-b1e9-16efb70c9784 | rabbit://openstack:****@controller-0 |    mysql+pymysql://nova:****@controller-0/nova    |
+-------+--------------------------------------+--------------------------------------+---------------------------------------------------+
```

##### 重启nova服务并设置开机自启动
```shell
systemctl enable openstack-nova-api.service \
  openstack-nova-consoleauth.service openstack-nova-scheduler.service \
  openstack-nova-conductor.service openstack-nova-novncproxy.service
systemctl restart openstack-nova-api.service \
  openstack-nova-consoleauth.service openstack-nova-scheduler.service \
  openstack-nova-conductor.service openstack-nova-novncproxy.service
  
```
```shell
[root@controller-0 ~]# systemctl enable openstack-nova-api.service \
>   openstack-nova-consoleauth.service openstack-nova-scheduler.service \
>   openstack-nova-conductor.service openstack-nova-novncproxy.service
leauth.service openstack-nova-scheduler.service \
  openstack-nova-conductor.service openstack-nova-novncproxy.serviceCreated symlink from /etc/systemd/system/multi-user.target.wants/openstack-nova-api.service to /usr/lib/systemd/system/openstack-nova-api.service.
Created symlink from /etc/systemd/system/multi-user.target.wants/openstack-nova-consoleauth.service to /usr/lib/systemd/system/openstack-nova-consoleauth.service.
Created symlink from /etc/systemd/system/multi-user.target.wants/openstack-nova-scheduler.service to /usr/lib/systemd/system/openstack-nova-scheduler.service.
Created symlink from /etc/systemd/system/multi-user.target.wants/openstack-nova-conductor.service to /usr/lib/systemd/system/openstack-nova-conductor.service.
Created symlink from /etc/systemd/system/multi-user.target.wants/openstack-nova-novncproxy.service to /usr/lib/systemd/system/openstack-nova-novncproxy.service.
[root@controller-0 ~]# systemctl restart openstack-nova-api.service \
>   openstack-nova-consoleauth.service openstack-nova-scheduler.service \
>   openstack-nova-conductor.service openstack-nova-novncproxy.service
[root@controller-0 ~]# 
```

#### 安装nova计算节点操作

###### yum安装计算节点 nova rpm包
```shell
yum install openstack-nova-compute
```
###### 配置/etc/nova/nova.conf文件
```shell
#  In the [DEFAULT] section, enable only the compute and metadata APIs:
VALUE="osapi_compute,metadata"; FILE=/etc/nova/nova.conf; KEY="enabled_apis"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# In the [DEFAULT] section, configure RabbitMQ message queue access:
VALUE="rabbit://openstack:openstack123@controller-0"; FILE=/etc/nova/nova.conf; KEY="transport_url"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# In the [api] and [keystone_authtoken] sections, configure Identity service access:
# api auth_strategy
VALUE="keystone"; FILE=/etc/nova/nova.conf; KEY="auth_strategy"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi


# keystone_authtoken
VALUE="auth_uri = http://controller-0:5000\nauth_url = http://controller-0:35357\nmemcached_servers = controller-0:11211\nauth_type = password\nproject_domain_name = default\nuser_domain_name = default\nproject_name = service\nusername = nova\npassword = nova"; FILE=/etc/nova/nova.conf; KEY="\[keystone_authtoken\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# In the [DEFAULT] section, configure the my_ip option to use the management interface IP address of the compute  node:
# my_ip
VALUE="192.168.8.202"; FILE=/etc/nova/nova.conf; KEY="my_ip"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# In the [DEFAULT] section, enable support for the Networking service:
VALUE="True"; FILE=/etc/nova/nova.conf; KEY="use_neutron"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

VALUE="nova.virt.firewall.NoopFirewallDriver"; FILE=/etc/nova/nova.conf; KEY="firewall_driver"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# vnc enabled
VALUE="enabled = True"; FILE=/etc/nova/nova.conf; KEY="\[vnc\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# vncserver_listen 
VALUE="0.0.0.0"; FILE=/etc/nova/nova.conf; KEY="vncserver_listen"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# vncserver_proxyclient_address
VALUE="\$my_ip"; FILE=/etc/nova/nova.conf; KEY="vncserver_proxyclient_address"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#novncproxy_base_url 
VALUE="http://controller-0:6080/vnc_auto.html"; FILE=/etc/nova/nova.conf; KEY="novncproxy_base_url"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# In the [glance] section, configure the location of the Image service API:
# api_servers
VALUE="http://controller-0:9292"; FILE=/etc/nova/nova.conf; KEY="api_servers"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#In the [oslo_concurrency] section, configure the lock path:
VALUE="/var/lib/nova/tmp"; FILE=/etc/nova/nova.conf; KEY="lock_path"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# In the [placement] section, configure the Placement API:
VALUE="os_region_name = RegionOne\nproject_domain_name = Default\nproject_name = service\nauth_type = password\nuser_domain_name = Default\nauth_url = http://controller-0:35357/v3\nusername = placement\npassword = placement"; FILE=/etc/nova/nova.conf; KEY="\[placement\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```

###### 检查Compute节点CPU对虚拟化的支持情况
```shell
egrep -c '(vmx|svm)' /proc/cpuinfo

######如果没有返回值，或者返回值为0.修改配置文件
[libvirt]
virt_type=qemu
#In the [oslo_concurrency] section, configure the lock path:
VALUE="qemu"; FILE=/etc/nova/nova.conf; KEY="virt_type"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```

###### 重启nova-compute相关服务并配置开机自启动
```shell
systemctl enable libvirtd.service openstack-nova-compute.service
systemctl restart libvirtd.service openstack-nova-compute.service
systemctl status libvirtd.service openstack-nova-compute.service
```



### 安装Dashboard(控制节点)
####  yum安装dashborad rpm包
```shell
yum -y install openstack-dashboard
```

#### 修改Dashboard的配置文件
```shell
#Configure the dashboard to use OpenStack services on the controller node:
VALUE="\"controller-0\""; FILE=/etc/openstack-dashboard/local_settings; KEY="OPENSTACK_HOST"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#Allow your hosts to access the dashboard:
VALUE="\['horizon.example.com', 'localhost','192.168.8.201'\]\nSESSION_ENGINE = 'django.contrib.sessions.backends.cache'"; FILE=/etc/openstack-dashboard/local_settings; KEY="ALLOWED_HOSTS"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi


#Configure the memcached session storage service:

#SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
VALUE="CACHES = {\n    'default': {\n         'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',\n         'LOCATION': 'controller-0:11211',\n    }\n}";KEY="^CACHES = "; APP_LINE=5; FILE=/etc/openstack-dashboard/local_settings; NEW_VALUE="$VALUE"; read B_LINE S_LINE E_LINE <<< $(grep -n -A $APP_LINE "$KEY" $FILE | sed 's|-|:|' | awk -F':' '{if (NR==1 || NR==2) print $1;} END{print $1}'); echo $B_LINE $S_LINE $E_LINE; sed -i "${S_LINE},${E_LINE}d" $FILE; sed -i "${B_LINE}s|.*|$NEW_VALUE|" $FILE;

#OPENSTACK_KEYSTONE_URL 
VALUE="\"http://%s:5000/v3\" %OPENSTACK_HOST"; FILE=/etc/openstack-dashboard/local_settings; KEY="OPENSTACK_KEYSTONE_URL"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# OPENSTACK_KEYSTONE_MULTIDOMAIN_SUPPORT 
VALUE="True"; FILE=/etc/openstack-dashboard/local_settings; KEY="OPENSTACK_KEYSTONE_MULTIDOMAIN_SUPPORT "; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi


#OPENSTACK_API_VERSIONS 
VALUE="OPENSTACK_API_VERSIONS = {\n   "identity": 3,\n   "image": 2,\n   "volume": 2,\n}";KEY="OPENSTACK_API_VERSIONS"; APP_LINE=6; FILE=/etc/openstack-dashboard/local_settings; NEW_VALUE="$VALUE"; read B_LINE S_LINE E_LINE <<< $(grep -n -A $APP_LINE "$KEY" $FILE | sed 's|-|:|' | awk -F':' '{if (NR==1 || NR==2) print $1;} END{print $1}'); echo $B_LINE $S_LINE $E_LINE; sed -i "${S_LINE},${E_LINE}d" $FILE; sed -i "${B_LINE}s|.*|$NEW_VALUE|" $FILE;

#OPENSTACK_KEYSTONE_DEFAULT_DOMAIN 
VALUE="\"Default\""; FILE=/etc/openstack-dashboard/local_settings; KEY="OPENSTACK_KEYSTONE_DEFAULT_DOMAIN ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#OPENSTACK_KEYSTONE_DEFAULT_ROLE 
VALUE="\"user\""; FILE=/etc/openstack-dashboard/local_settings; KEY="OPENSTACK_KEYSTONE_DEFAULT_ROLE ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#OPENSTACK_NEUTRON_NETWORK 
VALUE="OPENSTACK_NEUTRON_NETWORK = {\n   'enable_router': False,\n   'enable_quotas': False,\n   'enable_distributed_router': False,\n   'enable_ha_router': False,\n   'enable_lb':False,\n   'enable_firewall': False,\n   'enable_vpn':False,\n   'enable_fip_topology_check':False,\n";KEY="^OPENSTACK_NEUTRON_NETWORK"; APP_LINE=8; FILE=/etc/openstack-dashboard/local_settings; NEW_VALUE="$VALUE"; read B_LINE S_LINE E_LINE <<< $(grep -n -A $APP_LINE "$KEY" $FILE | sed 's|-|:|' | awk -F':' '{if (NR==1 || NR==2) print $1;} END{print $1}'); echo $B_LINE $S_LINE $E_LINE; sed -i "${S_LINE},${E_LINE}d" $FILE; sed -i "${B_LINE}s|.*|$NEW_VALUE|" $FILE;

#TIME_ZONE 
VALUE="\"TIME_ZONE\""; FILE=/etc/openstack-dashboard/local_settings; KEY="TIME_ZONE ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```
#### 控制节点上执行的命令
```shell
#Run the following commands on the controller node.
openstack compute service list --service nova-compute

#Discover compute hosts:
su -s /bin/sh -c "nova-manage cell_v2 discover_hosts --verbose" nova
```
```shell
[root@controller-0 ~]# openstack compute service list --service nova-compute
+----+--------------+-----------+------+---------+-------+----------------------------+
| ID | Binary       | Host      | Zone | Status  | State | Updated At                 |
+----+--------------+-----------+------+---------+-------+----------------------------+
|  9 | nova-compute | compute-0 | nova | enabled | up    | 2020-08-12T06:50:22.000000 |
+----+--------------+-----------+------+---------+-------+----------------------------+

[root@controller-0 ~]# su -s /bin/sh -c "nova-manage cell_v2 discover_hosts --verbose" nova
Found 2 cell mappings.
Skipping cell0 since it does not contain hosts.
Getting computes from cell 'cell1': 4e86b81d-4046-40b1-b1e9-16efb70c9784
Checking host mapping for compute host 'compute-0': a1120efe-0a8a-4387-9dcd-0426b820512d
Creating host mapping for compute host 'compute-0': a1120efe-0a8a-4387-9dcd-0426b820512d
Found 1 unmapped computes in cell: 4e86b81d-4046-40b1-b1e9-16efb70c9784
```

```note
Note
When you add new compute nodes, you must run nova-manage cell_v2 discover_hosts on the controller node to register those new compute nodes. Alternatively, you can set an appropriate interval in /etc/nova/nova.conf:
```
```shell
#discover_hosts_in_cells_interval 
VALUE="300"; FILE=/etc/nova/nova.conf; KEY="discover_hosts_in_cells_interval"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```


#### 启动Dashboard服务
```shell

 systemctl restart httpd.service memcached.service
```

#### 验证Dashboard是否可以登录
```shell

http://192.168.56.101(controller-ip)/dashboard
http://192.168.8.201/dashboard
域名：Default 用户：admin 密码：admin
```
#### 控制节点放通防火墙端口
##### 配置防火墙策略
```shell
#iptables -t filter -A INPUT -p tcp --dport 80 -j ACCEPT
#iptables -t filter -A OUTPUT -p tcp --sport 80 -j ACCEPT
#iptables -t filter -A INPUT -p udp --dport 80 -j ACCEPT
#iptables -t filter -A OUTPUT -p udp --sport 80 -j ACCEPT

#systemctl restart firewalld

# 开放端口
firewall-cmd --permanent --add-port=80/tcp
firewall-cmd --permanent --add-port=5672/tcp
firewall-cmd --permanent --add-port=35357/tcp
#firewall-cmd --permanent --add-port=80/udp

# 移除端口
#firewall-cmd --permanent --remove-port=80/tcp
#firewall-cmd --permanent --remove-port=80/udp

# 重启防火墙
firewall-cmd --reload


# 查询端口是否开放
firewall-cmd --query-port=80/tcp
firewall-cmd --query-port=5672/tcp
firewall-cmd --query-port=35357/tcp
#firewall-cmd --query-port=80/udp
```

### 安装Neutron
#### 在MySQL节点配置neutron数据库
```shell
mysql -uroot -proot -e "CREATE DATABASE neutron;"; 
mysql -uroot -proot -e "GRANT ALL ON neutron.* TO 'neutron'@'localhost' IDENTIFIED BY 'neutron';";
mysql -uroot -proot -e "GRANT ALL ON neutron.* TO 'neutron'@'%' IDENTIFIED BY 'neutron';"; 
```

#### 在Keystone配置neutron的用户和角色
```shell
# neutron
openstack user create --domain default --password-prompt neutron
openstack role add --project service --user neutron admin

openstack service create --name neutron  --description "OpenStack Networking" network
openstack endpoint create --region RegionOne  network public http://controller-0:9696
openstack endpoint create --region RegionOne  network internal http://controller-0:9696
openstack endpoint create --region RegionOne  network admin http://controller-0:9696
```
```shell
[root@controller-0 ~]# source /root/admin-openrc.sh 
[root@controller-0 ~]# openstack user create --domain default --password-prompt neutron
# neutron用户的密码
User Password:
Repeat User Password:
+---------------------+----------------------------------+
| Field               | Value                            |
+---------------------+----------------------------------+
| domain_id           | default                          |
| enabled             | True                             |
| id                  | d92da150bd764d79aa8b78bdc55e3c99 |
| name                | neutron                          |
| options             | {}                               |
| password_expires_at | None                             |
+---------------------+----------------------------------+
[root@controller-0 ~]# openstack role add --project service --user neutron admin
[root@controller-0 ~]# openstack service create --name neutron  --description "OpenStack Networking" network
696
openstack endpoint create --region RegionOne  network admin http://controller-0:9696
+-------------+----------------------------------+
| Field       | Value                            |
+-------------+----------------------------------+
| description | OpenStack Networking             |
| enabled     | True                             |
| id          | 8518992fc5aa4d14870399e85a26794a |
| name        | neutron                          |
| type        | network                          |
+-------------+----------------------------------+
[root@controller-0 ~]# openstack endpoint create --region RegionOne  network public http://controller-0:9696
+--------------+----------------------------------+
| Field        | Value                            |
+--------------+----------------------------------+
| enabled      | True                             |
| id           | 903dcbf65f6248fcabf5f2bc5adc05b8 |
| interface    | public                           |
| region       | RegionOne                        |
| region_id    | RegionOne                        |
| service_id   | 8518992fc5aa4d14870399e85a26794a |
| service_name | neutron                          |
| service_type | network                          |
| url          | http://controller-0:9696         |
+--------------+----------------------------------+
[root@controller-0 ~]# openstack endpoint create --region RegionOne  network internal http://controller-0:9696
+--------------+----------------------------------+
| Field        | Value                            |
+--------------+----------------------------------+
| enabled      | True                             |
| id           | 431a587950a54738bda627a97cdda7f9 |
| interface    | internal                         |
| region       | RegionOne                        |
| region_id    | RegionOne                        |
| service_id   | 8518992fc5aa4d14870399e85a26794a |
| service_name | neutron                          |
| service_type | network                          |
| url          | http://controller-0:9696         |
+--------------+----------------------------------+
[root@controller-0 ~]# openstack endpoint create --region RegionOne  network admin http://controller-0:9696
+--------------+----------------------------------+
| Field        | Value                            |
+--------------+----------------------------------+
| enabled      | True                             |
| id           | 979a798377c444da904891da55099a6b |
| interface    | admin                            |
| region       | RegionOne                        |
| region_id    | RegionOne                        |
| service_id   | 8518992fc5aa4d14870399e85a26794a |
| service_name | neutron                          |
| service_type | network                          |
| url          | http://controller-0:9696         |
+--------------+----------------------------------+
```

#### 安装Neutron包，使用ml2作为二层core_plugin
```shell
yum install -y openstack-neutron openstack-neutron-ml2  ebtables
# ml2使用linuxbridge
yum install -y openstack-neutron-linuxbridge 

# ml2使用ovs
yum openstack-neutron-openvswitch

```

#### 修改neturon配置文件/etc/neutron/neutron.conf
```shell
# connection
VALUE="mysql+pymysql://neutron:neutron@controller-0/neutron"; FILE=/etc/neutron/neutron.conf; KEY="connection ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#core_plugin
VALUE="ml2"; FILE=/etc/neutron/neutron.conf; KEY="core_plugin ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#service_plugins
VALUE="router"; FILE=/etc/neutron/neutron.conf; KEY="service_plugins ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#allow_overlapping_ips 
VALUE="True"; FILE=/etc/neutron/neutron.conf; KEY="allow_overlapping_ips ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#transport_url 
VALUE="rabbit://openstack:openstack123@controller-0"; FILE=/etc/neutron/neutron.conf; KEY="transport_url ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#auth_strategy
VALUE="keystone"; FILE=/etc/neutron/neutron.conf; KEY="auth_strategy ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#notify_nova_on_port_status_changes
VALUE="True"; FILE=/etc/neutron/neutron.conf; KEY="notify_nova_on_port_status_changes ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#notify_nova_on_port_data_changes
VALUE="True"; FILE=/etc/neutron/neutron.conf; KEY="notify_nova_on_port_data_changes ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# keystone_authtoken
VALUE="auth_uri = http://controller-0:5000\nauth_url = http://controller-0:35357\nmemcached_servers = controller-0:11211\nauth_type = password\nproject_domain_name = default\nuser_domain_name = default\nproject_name = service\nusername = neutron\npassword = neutron"; FILE=/etc/neutron/neutron.conf; KEY="\[keystone_authtoken\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#nova
VALUE="auth_url = http://controller-0:35357\nauth_type = password\nproject_domain_name = default\nuser_domain_name = default\nregion_name = RegionOne\nproject_name = service\nusername = nova\npassword = nova"; FILE=/etc/neutron/neutron.conf; KEY="\[nova\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#[oslo_concurrency] lock_path
VALUE="/var/lib/neutron/tmp"; FILE=/etc/neutron/neutron.conf; KEY="lock_path"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```

#### 配置ML2配置文件

##### 修改/etc/neutron/plugins/ml2/ml2_conf.ini
```shell

#type_drivers
VALUE="vlan,vxlan,flat"; FILE=/etc/neutron/plugins/ml2/ml2_conf.ini; KEY="type_drivers"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#tenant_network_types
VALUE="vxlan,vlan,flat"; FILE=/etc/neutron/plugins/ml2/ml2_conf.ini; KEY="tenant_network_types"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#mechanism_drivers linuxbrange
VALUE="linuxbridge,l2population"; FILE=/etc/neutron/plugins/ml2/ml2_conf.ini; KEY="mechanism_drivers"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#mechanism_drivers openvswitch
VALUE="openvswitch,l2population"; FILE=/etc/neutron/plugins/ml2/ml2_conf.ini; KEY="mechanism_drivers"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#extension_drivers
VALUE="port_security"; FILE=/etc/neutron/plugins/ml2/ml2_conf.ini; KEY="extension_drivers"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m2 $FILE | awk -F ':' 'END{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#flat_networks
VALUE="service"; FILE=/etc/neutron/plugins/ml2/ml2_conf.ini; KEY="flat_networks"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# ml2_type_vxlan vni_ranges 
VALUE="1:65535"; FILE=/etc/neutron/plugins/ml2/ml2_conf.ini; KEY="vni_ranges"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m2 $FILE | awk -F ':' 'END{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# network_vlan_ranges
VALUE="external:2259:2260,service:2246:2258,management"; FILE=/etc/neutron/plugins/ml2/ml2_conf.ini; KEY="network_vlan_ranges"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m2 $FILE | awk -F ':' 'END{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#enable_ipset
VALUE="True"; FILE=/etc/neutron/plugins/ml2/ml2_conf.ini; KEY="enable_ipset"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

```

#### 配置/etc/neutron/metadata_agent.ini文件
```shell

VALUE="controller-0"; FILE=/etc/neutron/metadata_agent.ini; KEY="nova_metadata_host"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

VALUE="metadata"; FILE=/etc/neutron/metadata_agent.ini; KEY="metadata_proxy_shared_secret"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```

#### 配置Nova使用Neutron提供的网络服务
##### 修改/etc/nova/nova.conf
```shell
#neutron
VALUE="url = http://controller-0:9696\nauth_url = http://controller-0:35357\nauth_type = password\nproject_domain_name = default\nuser_domain_name = default\nregion_name = RegionOne\nproject_name = service\nusername = neutron\npassword = neutron\nservice_metadata_proxy = True\nmetadata_proxy_shared_secret = metadata"; FILE=/etc/nova/nova.conf; KEY="\[neutron\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "^$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

```

##### 建立ml2_conf.ini到plugin.ini的软连接
```shell
ln -s /etc/neutron/plugins/ml2/ml2_conf.ini /etc/neutron/plugin.ini
```

##### 生成Neutron的数据库
```shell
su -s /bin/sh -c "neutron-db-manage --config-file /etc/neutron/neutron.conf --config-file /etc/neutron/plugins/ml2/ml2_conf.ini upgrade head" neutron
```

##### Restart the Compute API service:
```shell
systemctl restart openstack-nova-api.service
systemctl enable neutron-server.service
systemctl restart neutron-server.service
```

### 配置网络节点


#### 修改/etc/sysctl.conf
```shell
#net.ipv4.ip_forward=1
VALUE="1"; FILE=/etc/sysctl.conf; KEY="net.ipv4.ip_forward"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#net.ipv4.conf.all.rp_filter=0
VALUE="0"; FILE=/etc/sysctl.conf; KEY="net.ipv4.conf.all.rp_filter"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#net.ipv4.conf.default.rp_filter=0
VALUE="0"; FILE=/etc/sysctl.conf; KEY="net.ipv4.conf.default.rp_filter"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

```

#### 重新加载系统配置
```shell
sysctl -p
```

####  安装Openstack的网络服务
```shell
yum install -y openstack-neutron openstack-neutron-ml2 ebtables
# ml2使用linuxbridge
yum install -y openstack-neutron-linuxbridge 

# ml2使用ovs
yum openstack-neutron-openvswitch
```

#### 配置/etc/neutron/neutron.conf文件
* **控制和网络节点合部不用再修改此配置文件**
```shell
#core_plugin
VALUE="ml2"; FILE=/etc/neutron/neutron.conf; KEY="core_plugin ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#service_plugins
VALUE="router"; FILE=/etc/neutron/neutron.conf; KEY="service_plugins ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#allow_overlapping_ips 
VALUE="True"; FILE=/etc/neutron/neutron.conf; KEY="allow_overlapping_ips ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#transport_url 
VALUE="rabbit://openstack:openstack123@controller-0"; FILE=/etc/neutron/neutron.conf; KEY="transport_url ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#auth_strategy
VALUE="keystone"; FILE=/etc/neutron/neutron.conf; KEY="auth_strategy ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# keystone_authtoken
VALUE="auth_uri = http://controller-0:5000\nauth_url = http://controller-0:35357\nmemcached_servers = controller-0:11211\nauth_type = password\nproject_domain_name = default\nuser_domain_name = default\nproject_name = service\nusername = neutron\npassword = neutron"; FILE=/etc/neutron/neutron.conf; KEY="\[keystone_authtoken\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#[oslo_concurrency] lock_path
VALUE="/var/lib/neutron/tmp"; FILE=/etc/neutron/neutron.conf; KEY="lock_path"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```

##### 修改/etc/neutron/plugins/ml2/ml2_conf.ini文件
* **控制和网络节点合布可以不用再修改此配置文件**
```shell

#type_drivers
VALUE="vlan,vxlan,flat"; FILE=/etc/neutron/plugins/ml2/ml2_conf.ini; KEY="type_drivers"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#tenant_network_types
VALUE="vxlan,vlan,flat"; FILE=/etc/neutron/plugins/ml2/ml2_conf.ini; KEY="tenant_network_types"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#mechanism_drivers linuxbrange
VALUE="linuxbridge,l2population"; FILE=/etc/neutron/plugins/ml2/ml2_conf.ini; KEY="mechanism_drivers"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#mechanism_drivers openvswitch
VALUE="openvswitch,l2population"; FILE=/etc/neutron/plugins/ml2/ml2_conf.ini; KEY="mechanism_drivers"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#extension_drivers
VALUE="port_security"; FILE=/etc/neutron/plugins/ml2/ml2_conf.ini; KEY="extension_drivers"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m2 $FILE | awk -F ':' 'END{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#flat_networks
VALUE="service"; FILE=/etc/neutron/plugins/ml2/ml2_conf.ini; KEY="flat_networks"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#network_vlan_ranges = external:2259:2260,service:2246:2258,management
VALUE="external:2259:2260,service:2246:2258,management"; FILE=/etc/neutron/plugins/ml2/ml2_conf.ini; KEY="network_vlan_ranges"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m2 $FILE | awk -F ':' 'END{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# ml2_type_vxlan vni_ranges 
VALUE="1:65535"; FILE=/etc/neutron/plugins/ml2/ml2_conf.ini; KEY="vni_ranges"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m2 $FILE | awk -F ':' 'END{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#enable_ipset
VALUE="True"; FILE=/etc/neutron/plugins/ml2/ml2_conf.ini; KEY="enable_ipset"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```

#### 配置Linux bridge agent

##### 修改/etc/neutron/plugins/ml2/linuxbridge_agent.ini
```shell
#physical_interface_mappings
VALUE="service:ens32"; FILE=/etc/neutron/plugins/ml2/linuxbridge_agent.ini; KEY="physical_interface_mappings"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#enable_vxlan
VALUE="True"; FILE=/etc/neutron/plugins/ml2/linuxbridge_agent.ini; KEY="enable_vxlan"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#local_ip
VALUE="192.168.8.201"; FILE=/etc/neutron/plugins/ml2/linuxbridge_agent.ini; KEY="local_ip"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#l2_population
VALUE="True"; FILE=/etc/neutron/plugins/ml2/linuxbridge_agent.ini; KEY="l2_population"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#enable_security_group
VALUE="True"; FILE=/etc/neutron/plugins/ml2/linuxbridge_agent.ini; KEY="enable_security_group"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#firewall_driver
VALUE="neutron.agent.linux.iptables_firewall.IptablesFirewallDriver"; FILE=/etc/neutron/plugins/ml2/linuxbridge_agent.ini; KEY="firewall_driver"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```



#### 配置ovs agent



##### 配置/etc/neutron/plugins/ml2/openvswitch_agent.ini

```shell
#agent
VALUE="tunnel_types=vxlan\nl2_population=True\nprevent_arp_spoofing=True; FILE=/etc/neutron/plugins/ml2/openvswitch_agent.ini; KEY="\[agent\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#local_ip
VALUE="192.168.8.201"; FILE=/etc/neutron/plugins/ml2/openvswitch_agent.ini; KEY="local_ip"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#bridge_mappings
VALUE="service:br-ex"; FILE=/etc/neutron/plugins/ml2/openvswitch_agent.ini; KEY="bridge_mappings"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#firewall_driver
VALUE="iptables_hybrid"; FILE=/etc/neutron/plugins/ml2/openvswitch_agent.ini; KEY="firewall_driver"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#enable_security_group
VALUE="True"; FILE=/etc/neutron/plugins/ml2/openvswitch_agent.ini; KEY="enable_security_group"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

```



#### 配置l3_agent.ini

* /etc/neutron/l3_agent.ini

```shell
#interface_driver linuxbridge
VALUE="linuxbridge"; FILE=/etc/neutron/l3_agent.ini; KEY="interface_driver"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#interface_driver ovs
VALUE="neutron.agent.linux.interface.OVSInterfaceDriver"; FILE=/etc/neutron/l3_agent.ini; KEY="interface_driver"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi


```

#### 配置DHCP Agent
##### 修改/etc/neutron/dhcp_agent.ini
```shell
#interface_driver 
# linuxbridge
VALUE="linuxbridge"; FILE=/etc/neutron/dhcp_agent.ini; KEY="interface_driver"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#interface_driver 
# ovs
VALUE="neutron.agent.linux.interface.OVSInterfaceDriver"; FILE=/etc/neutron/dhcp_agent.ini; KEY="interface_driver"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#dhcp_driver
VALUE="neutron.agent.linux.dhcp.Dnsmasq"; FILE=/etc/neutron/dhcp_agent.ini; KEY="dhcp_driver"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#enable_isolated_metadata
VALUE="True"; FILE=/etc/neutron/dhcp_agent.ini; KEY="enable_isolated_metadata"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```

#### 配置metadata agent
##### 修改/etc/neutron/metadata_agent.ini
* **控制和网络节点合布可以不用再修改此配置文件**
```shell

VALUE="controller-0"; FILE=/etc/neutron/metadata_agent.ini; KEY="nova_metadata_host"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

VALUE="metadata"; FILE=/etc/neutron/metadata_agent.ini; KEY="metadata_proxy_shared_secret"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```

#### 建立ml2_conf.ini到plugin.ini的软连接
* **控制和网络节点合布可以不用再修改此配置文件**
```shell
 ln -s /etc/neutron/plugins/ml2/ml2_conf.ini /etc/neutron/plugin.ini
```

#### 启动服务
```shell
systemctl enable neutron-dhcp-agent.service 
systemctl enable neutron-metadata-agent.service
systemctl enable neutron-l3-agent.service

systemctl restart neutron-dhcp-agent.service 
systemctl restart neutron-metadata-agent.service
systemctl restart neutron-l3-agent.service

# linuxbridge
systemctl enable neutron-linuxbridge-agent.service 
systemctl restart neutron-linuxbridge-agent.service

# ovs
systemctl enable neutron-openvswitch-agent.service
systemctl restart neutron-openvswitch-agent.service
```
```shell
[root@controller-0 ~]# systemctl enable neutron-linuxbridge-agent.service neutron-dhcp-agent.service neutron-metadata-agent.service
vice
systemctl restart neutron-l3-agent.serviceCreated symlink from /etc/systemd/system/multi-user.target.wants/neutron-linuxbridge-agent.service to /usr/lib/systemd/system/neutron-linuxbridge-agent.service.
Created symlink from /etc/systemd/system/multi-user.target.wants/neutron-dhcp-agent.service to /usr/lib/systemd/system/neutron-dhcp-agent.service.
Created symlink from /etc/systemd/system/multi-user.target.wants/neutron-metadata-agent.service to /usr/lib/systemd/system/neutron-metadata-agent.service.
[root@controller-0 ~]# systemctl restart neutron-linuxbridge-agent.service neutron-dhcp-agent.service neutron-metadata-agent.service
[root@controller-0 ~]# systemctl enable neutron-l3-agent.service
[root@controller-0 ~]# systemctl restart neutron-l3-agent.service
```

#### 建立并重启neutron-openvswitch-agent服务

```shell
yum install openstack-neutron-openvswitch -y
systemctl enable neutron-openvswitch-agent.service
systemctl restart neutron-openvswitch-agent.service
systemctl status neutron-openvswitch-agent.service

```
```shell

systemctl enable neutron-openvswitch-agent.service 
systemctl enable neutron-l3-agent.service 
systemctl enable neutron-dhcp-agent.service 
systemctl enable neutron-metadata-agent.service 
systemctl enable neutron-ovs-cleanup.service

systemctl restart neutron-l3-agent.service 
systemctl restart neutron-dhcp-agent.service 
systemctl restart neutron-metadata-agent.service

systemctl restart neutron-openvswitch-agent.service
```

### 配置计算节点
#### 修改/etc/sysctl.conf
```shell
#net.ipv4.ip_forward=1
VALUE="1"; FILE=/etc/sysctl.conf; KEY="net.ipv4.ip_forward"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#net.ipv4.conf.all.rp_filter=0
VALUE="0"; FILE=/etc/sysctl.conf; KEY="net.ipv4.conf.all.rp_filter"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#net.ipv4.conf.default.rp_filter=0
VALUE="0"; FILE=/etc/sysctl.conf; KEY="net.ipv4.conf.default.rp_filter"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

```


#### 重新加载系统配置
```shell
sysctl -p
```

#### 安装neutron的二层Agent
```shell
yum install -y  ebtables ipset
# linuxbridge
yum install -y openstack-neutron-linuxbridge
# ovs
yum install -y openstack-neutron-openvswitch
```

#### 配置/etc/neutron/neutron.conf文件
* **控制和网络节点合布可以不用再修改此配置文件**
```shell
#transport_url 
VALUE="rabbit://openstack:openstack123@controller-0"; FILE=/etc/neutron/neutron.conf; KEY="transport_url ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#auth_strategy
VALUE="keystone"; FILE=/etc/neutron/neutron.conf; KEY="auth_strategy ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#rabbit_host
VALUE="controller-0"; FILE=/etc/neutron/neutron.conf; KEY="rabbit_host"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#rabbit_userid
VALUE="openstack"; FILE=/etc/neutron/neutron.conf; KEY="rabbit_userid"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#rabbit_password
VALUE="openstack123"; FILE=/etc/neutron/neutron.conf; KEY="rabbit_password"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# keystone_authtoken
VALUE="auth_uri = http://controller-0:5000\nauth_url = http://controller-0:35357\nmemcached_servers = controller-0:11211\nauth_type = password\nproject_domain_name = default\nuser_domain_name = default\nproject_name = service\nusername = neutron\npassword = neutron"; FILE=/etc/neutron/neutron.conf; KEY="\[keystone_authtoken\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#[oslo_concurrency] lock_path
VALUE="/var/lib/neutron/tmp"; FILE=/etc/neutron/neutron.conf; KEY="lock_path"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```

#### 配置Linux bridge agent

##### 修改/etc/neutron/plugins/ml2/linuxbridge_agent.ini
```shell
#physical_interface_mappings
VALUE="service:ens32"; FILE=/etc/neutron/plugins/ml2/linuxbridge_agent.ini; KEY="physical_interface_mappings"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#enable_vxlan
VALUE="True"; FILE=/etc/neutron/plugins/ml2/linuxbridge_agent.ini; KEY="enable_vxlan"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#local_ip
VALUE="192.168.8.202"; FILE=/etc/neutron/plugins/ml2/linuxbridge_agent.ini; KEY="local_ip"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#l2_population
VALUE="True"; FILE=/etc/neutron/plugins/ml2/linuxbridge_agent.ini; KEY="l2_population"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#enable_security_group
VALUE="True"; FILE=/etc/neutron/plugins/ml2/linuxbridge_agent.ini; KEY="enable_security_group"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#firewall_driver
VALUE="neutron.agent.linux.iptables_firewall.IptablesFirewallDriver"; FILE=/etc/neutron/plugins/ml2/linuxbridge_agent.ini; KEY="firewall_driver"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```



#### 配置ovs agent

##### 配置/etc/neutron/plugins/ml2/openvswitch_agent.ini

```shell
#agent
VALUE="tunnel_types=vxlan\nl2_population=True\nprevent_arp_spoofing=True"; FILE="/etc/neutron/plugins/ml2/openvswitch_agent.ini"; KEY="\[agent\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#local_ip
VALUE="192.168.8.202"; FILE=/etc/neutron/plugins/ml2/openvswitch_agent.ini; KEY="local_ip"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#bridge_mappings
VALUE="service:br-ex"; FILE=/etc/neutron/plugins/ml2/openvswitch_agent.ini; KEY="bridge_mappings"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#firewall_driver
VALUE="iptables_hybrid"; FILE=/etc/neutron/plugins/ml2/openvswitch_agent.ini; KEY="firewall_driver"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#enable_security_group
VALUE="True"; FILE=/etc/neutron/plugins/ml2/openvswitch_agent.ini; KEY="enable_security_group"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

```





#### 修改/etc/nova/nova.conf

```shell
#neutron
VALUE="url = http://controller-0:9696\nauth_url = http://controller-0:35357\nauth_type = password\nproject_domain_name = default\nuser_domain_name = default\nregion_name = RegionOne\nproject_name = service\nusername = neutron\npassword = neutron\nservice_metadata_proxy = True\nmetadata_proxy_shared_secret = metadata"; FILE=/etc/nova/nova.conf; KEY="\[neutron\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "^$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

```

#### 重启计算节点服务

##### 重启nova-compute
```shell
systemctl restart openstack-nova-compute.service
```

##### 重启neutron-linuxbridge-agent.service
```shell
systemctl enable neutron-linuxbridge-agent.service
systemctl start neutron-linuxbridge-agent.service
```



##### 重启neutron-openvswitch-agent.service

```shell
# ovs
systemctl enable neutron-openvswitch-agent.service
systemctl restart neutron-openvswitch-agent.service
```



### 配置ovs的网桥(所有节点)

```shell
ovs-vsctl add-br br-ex
ovs-vsctl add-port br-ex ens32
ovs-vsctl list-ports br-ex
```



#### 配置网桥的配置文件

```shell
BR0=br-ex
IP=192.168.8.201
IP_MASK=255.255.255.0
GATEWAY_IP=192.168.8.254
NET_TYPE=OVSBridge 
DEVICETYPE_VALUE=ovs
tee /etc/sysconfig/network-scripts/ifcfg-br-ex << EOF
NAME=$BR0
DEVICE=$BR0
ONBOOT=yes
TYPE=$NET_TYPE
DEVICETYPE=$DEVICETYPE_VALUE
IPADDR=$IP
NETMASK=$IP_MASK
GATEWAY=$GATEWAY_IP
EOF


ETH0=ens32
NET_TYPE=OVSIntPort
BR=br-ex
DEVICETYPE_VALUE=ovs
tee  /etc/sysconfig/network-scripts/ifcfg-ens32 << EOF
NAME=$ETH0
DEVICE=$ETH0
ONBOOT=yes
NETBOOT=yes
BOOTPROTO=static
TYPE=$NET_TYPE
OVS_BRIDGE=$BR
DEVICETYPE=$DEVICETYPE_VALUE
EOF

```



#### 重启网络服务

```shell
systemctl restart network
ovs-vsctl del-port br-ex ens32
ovs-vsctl add-port br-ex ens32
```



### 安装VPN服务

**注意事项：neutron-vpn-agent与neutron-l3-agent不能同时部署运行**

#### Controller，Network节点上安装openstack-neutron-vpnaas
```shell
yum install -y openstack-neutron-vpnaas
```

##### 在Network节点上安装libreswan
**注：可以选择多种方式，此处使用的是libreswan。**

**libreswan的安装版本请使用3.15或3.16版本**
```shell
yum install -y libreswan
```

##### 修改/etc/sysctl.conf
* **控制和网络节点同一个已经执行过了可以不执行**
```shell
sysctl -a | egrep"ipv4.*(accept|send)_redirects" | awk -F "=" '{print$1"= 0"}' >> /etc/sysctl.conf

#net.ipv4.ip_forward=1
VALUE="1"; FILE=/etc/sysctl.conf; KEY="net.ipv4.ip_forward"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#net.ipv4.conf.all.rp_filter=0
VALUE="0"; FILE=/etc/sysctl.conf; KEY="net.ipv4.conf.all.rp_filter"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#net.ipv4.conf.default.rp_filter=0
VALUE="0"; FILE=/etc/sysctl.conf; KEY="net.ipv4.conf.default.rp_filter"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

sysctl -p
```

##### 验证OpenSWan是否正确安装
```shell
ipsec --version
```

##### 重启ipsec
```shell
systemctl restart ipsec

ipsec verify
```
```shell
[root@controller-0 ~]# systemctl start ipsec
[root@controller-0 ~]# ipsec verify
Verifying installed system and configuration files

Version check and ipsec on-path                   	[OK]
Libreswan 3.25 (netkey) on 3.10.0-1127.18.2.el7.x86_64
Checking for IPsec support in kernel              	[OK]
 NETKEY: Testing XFRM related proc values
         ICMP default/send_redirects              	[NOT DISABLED]

  Disable /proc/sys/net/ipv4/conf/*/send_redirects or NETKEY will act on or cause sending of bogus ICMP redirects!

         ICMP default/accept_redirects            	[NOT DISABLED]

  Disable /proc/sys/net/ipv4/conf/*/accept_redirects or NETKEY will act on or cause sending of bogus ICMP redirects!

         XFRM larval drop                         	[OK]
Pluto ipsec.conf syntax                           	[OK]
Two or more interfaces found, checking IP forwarding	[OK]
Checking rp_filter                                	[ENABLED]
 /proc/sys/net/ipv4/conf/ens32/rp_filter          	[ENABLED]
 /proc/sys/net/ipv4/conf/ens35/rp_filter          	[ENABLED]
  rp_filter is not fully aware of IPsec and should be disabled
Checking that pluto is running                    	[OK]
 Pluto listening for IKE on udp 500               	[OK]
 Pluto listening for IKE/NAT-T on udp 4500        	[OK]
 Pluto ipsec.secret syntax                        	[OK]
Checking 'ip' command                             	[OK]
Checking 'iptables' command                       	[OK]
Checking 'prelink' command does not interfere with FIPS	[OK]
Checking for obsolete ipsec.conf options          	[OBSOLETE KEYWORD]
warning: could not open include filename: '/etc/ipsec.d/*.conf'

ipsec verify: encountered 7 errors - see 'man ipsec_verify' for help
```

##### 修改/etc/neutron/neutron.conf 控制和网络节点
 ```shell
#service_plugins
VALUE="router,vpnaas"; FILE=/etc/neutron/neutron.conf; KEY="service_plugins ="; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# 此处改了就不用修改/etc/neutron/neutron_vpnaas.conf文件中的内容
# [service_providers] service_provider
VALUE="service_provider = VPN:libreswan:neutron_vpnaas.services.vpn.service_drivers.ipsec.IPsecVPNDriver:default"; FILE=/etc/neutron/neutron.conf; KEY="[service_providers]" GREP_KEY="\[service_providers\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "^$GREP_KEY" -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo -e "$NEW_VALUE" >> $FILE; fi
 ```

##### 修改/etc/neutron/vpn_agent.ini网络节点
```shell
#DEFAULT interface_driver linuxbridge
VALUE="interface_driver =linuxbridge"; FILE=/etc/neutron/vpn_agent.ini; KEY="\[DEFAULT\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi


#interface_driver ovs
VALUE="interface_driver = neutron.agent.linux.interface.OVSInterfaceDriver"; FILE=/etc/neutron/vpn_agent.ini; KEY="[DEFAULT]"; GREP_KEY="\[DEFAULT\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$GREP_KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#vpn_device_driver
VALUE="neutron_vpnaas.services.vpn.device_drivers.libreswan_ipsec.LibreSwanDriver"; FILE=/etc/neutron/vpn_agent.ini; KEY="vpn_device_driver"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```



##### 修改/etc/neutron/neutron_vpnaas.conf

```shell
# [service_providers] service_provider
VALUE="service_provider = VPN:libreswan:neutron_vpnaas.services.vpn.service_drivers.ipsec.IPsecVPNDriver:default"; FILE=/etc/neutron/neutron_vpnaas.conf; KEY="[service_providers]" GREP_KEY="\[service_providers\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "^$GREP_KEY" -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo -e "$NEW_VALUE" >> $FILE; fi
```



##### 创建DB表

```shell

neutron-db-manage --subproject neutron-vpnaas upgrade head

su -s /bin/sh -c "neutron-db-manage --config-file /etc/neutron/neutron.conf --config-file /etc/neutron/vpn_agent.ini --config-file /etc/neutron/neutron_vpnaas.conf upgrade head" neutron
```


##### 停止network结点上停止neutron-l3-agent
**注意事项：neutron-vpn-agent与neutron-l3-agent不能同时部署运行**
```shell
systemctl stop neutron-l3-agent.service
systemctl disable neutron-l3-agent.service
```

##### 安装dashboard插件 @openstack-dashboard的安装节点
* 下载代码插件
```shell
git clone https://github.com/openstack/neutron-vpnaas-dashboard.git
cd neutron-vpnaas-dashboard
python setup.py install
cp neutron_vpnaas_dashboard/enabled/_7100_project_vpn_panel.py* /usr/share/openstack-dashboard/openstack_dashboard/enabled/
```

##### 在openstack-dashboard的安装节点，/etc/openstack-dashboard/local_settings
```shell
#/etc/openstack-dashboard/local_settingsOPENSTACK_NEUTRON_NETWORK = {    'enable_vpn':True,}

#enable_vpn':True,
VALUE="True,"; FILE=/etc/openstack-dashboard/local_settings; KEY="enable_vpn"; NEW_VALUE="   '$KEY':$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```

##### 重启dashboard
```shell
systemctl restart httpd
```



### 重启所有服务



#### 控制重启所有服务

```shell
systemctl restart httpd
systemctl restart memcached.service
systemctl restart openstack-keystone
systemctl restart openstack-glance-api.service
systemctl restart openstack-glance-registry.service
systemctl restart openstack-nova-api.service
systemctl restart neutron-server.service
# linuxbridge
#systemctl restart neutron-linuxbridge-agent.service
systemctl restart neutron-dhcp-agent.service
systemctl restart neutron-metadata-agent.service
#systemctl restart neutron-l3-agent.service
# ovs
systemctl restart neutron-openvswitch-agent.service
systemctl restart neutron-vpn-agent

# nova
systemctl restart openstack-nova-api.service
systemctl restart openstack-nova-consoleauth.service 
systemctl restart openstack-nova-scheduler.service
systemctl restart openstack-nova-conductor.service
systemctl restart openstack-nova-novncproxy.service

systemctl stop neutron-linuxbridge-agent.service
systemctl disable neutron-linuxbridge-agent.service


systemctl list-units | grep switch
systemctl restart openvswitch.service
systemctl status openvswitch.service

```



#### 计算重所有服务

```shell 
systemctl restart openstack-nova-compute.service
# linuxbridge
#systemctl restart neutron-linuxbridge-agent.service
# ovs
systemctl restart neutron-openvswitch-agent.service
```



### 验证网络服务

```shell
openstack network create --internal  --provider-network-type vlan cf-network-internal

openstack subnet create cf-subnet-162.168.168.0-24 --ip-version 4 --subnet-range 162.168.168.0/24 --allocation-pool start=162.168.168.1,end=162.168.168.253 --gateway 162.168.168.254 --network ac3941d0-eb7c-4f95-9e58-9c7dd7babafa --no-dhcp
```
```shell
[root@controller-0 ~]# openstack network create --internal  --provider-network-type vlan cf-network-internal
+---------------------------+--------------------------------------+
| Field                     | Value                                |
+---------------------------+--------------------------------------+
| admin_state_up            | UP                                   |
| availability_zone_hints   |                                      |
| availability_zones        |                                      |
| created_at                | 2020-08-13T01:46:21Z                 |
| description               |                                      |
| dns_domain                | None                                 |
| id                        | ac3941d0-eb7c-4f95-9e58-9c7dd7babafa |
| ipv4_address_scope        | None                                 |
| ipv6_address_scope        | None                                 |
| is_default                | False                                |
| is_vlan_transparent       | None                                 |
| mtu                       | 1500                                 |
| name                      | cf-network-internal                  |
| port_security_enabled     | True                                 |
| project_id                | f70a8b7d3aa047bc8a278a401186500a     |
| provider:network_type     | vlan                                 |
| provider:physical_network | service                              |
| provider:segmentation_id  | 2257                                 |
| qos_policy_id             | None                                 |
| revision_number           | 2                                    |
| router:external           | Internal                             |
| segments                  | None                                 |
| shared                    | False                                |
| status                    | ACTIVE                               |
| subnets                   |                                      |
| tags                      |                                      |
| updated_at                | 2020-08-13T01:46:21Z                 |
+---------------------------+--------------------------------------+

[root@controller-0 ~]# openstack network create --internal  --provider-network-type vlan cf-network-internal-2
+---------------------------+--------------------------------------+
| Field                     | Value                                |
+---------------------------+--------------------------------------+
| admin_state_up            | UP                                   |
| availability_zone_hints   |                                      |
| availability_zones        |                                      |
| created_at                | 2020-08-13T11:29:30Z                 |
| description               |                                      |
| dns_domain                | None                                 |
| id                        | d91beeb4-312c-4e3e-8c6f-a7f38d9a51de |
| ipv4_address_scope        | None                                 |
| ipv6_address_scope        | None                                 |
| is_default                | False                                |
| is_vlan_transparent       | None                                 |
| mtu                       | 1500                                 |
| name                      | cf-network-internal-2                |
| port_security_enabled     | True                                 |
| project_id                | f70a8b7d3aa047bc8a278a401186500a     |
| provider:network_type     | vlan                                 |
| provider:physical_network | service                              |
| provider:segmentation_id  | 2258                                 |
| qos_policy_id             | None                                 |
| revision_number           | 2                                    |
| router:external           | Internal                             |
| segments                  | None                                 |
| shared                    | False                                |
| status                    | ACTIVE                               |
| subnets                   |                                      |
| tags                      |                                      |
| updated_at                | 2020-08-13T11:29:30Z                 |
+---------------------------+--------------------------------------+


[root@controller-0 ~]# openstack subnet create cf-subnet-162.168.168.0-24 --ip-version 4 --subnet-range 162.168.168.0/24 --allocation-pool start=162.168.168.1,end=162.168.168.253 --gateway 162.168.168.254 --network ac3941d0-eb7c-4f95-9e58-9c7dd7babafa --no-dhcp
+-------------------------+--------------------------------------+
| Field                   | Value                                |
+-------------------------+--------------------------------------+
| allocation_pools        | 162.168.168.1-162.168.168.253        |
| cidr                    | 162.168.168.0/24                     |
| created_at              | 2020-08-13T01:47:04Z                 |
| description             |                                      |
| dns_nameservers         |                                      |
| enable_dhcp             | False                                |
| gateway_ip              | 162.168.168.254                      |
| host_routes             |                                      |
| id                      | b582cb4b-9c75-4aa3-afe1-af7a93a64f77 |
| ip_version              | 4                                    |
| ipv6_address_mode       | None                                 |
| ipv6_ra_mode            | None                                 |
| name                    | cf-subnet-162.168.168.0-24           |
| network_id              | ac3941d0-eb7c-4f95-9e58-9c7dd7babafa |
| project_id              | f70a8b7d3aa047bc8a278a401186500a     |
| revision_number         | 0                                    |
| segment_id              | None                                 |
| service_types           |                                      |
| subnetpool_id           | None                                 |
| tags                    |                                      |
| updated_at              | 2020-08-13T01:47:04Z                 |
| use_default_subnet_pool | None                                 |
+-------------------------+--------------------------------------+

[root@controller-0 ~]# openstack subnet create cf-subnet-152.168.168.0-24 --ip-version 4 --subnet-range 152.168.168.0/24 --allocation-pool start=152.168.168.1,end=152.168.168.253 --gateway 152.168.168.254 --network d91beeb4-312c-4e3e-8c6f-a7f38d9a51de --no-dhcp
+-------------------------+--------------------------------------+
| Field                   | Value                                |
+-------------------------+--------------------------------------+
| allocation_pools        | 152.168.168.1-152.168.168.253        |
| cidr                    | 152.168.168.0/24                     |
| created_at              | 2020-08-13T11:31:24Z                 |
| description             |                                      |
| dns_nameservers         |                                      |
| enable_dhcp             | False                                |
| gateway_ip              | 152.168.168.254                      |
| host_routes             |                                      |
| id                      | ca02049b-af70-4538-8d8f-643c0418d5c6 |
| ip_version              | 4                                    |
| ipv6_address_mode       | None                                 |
| ipv6_ra_mode            | None                                 |
| name                    | cf-subnet-152.168.168.0-24           |
| network_id              | d91beeb4-312c-4e3e-8c6f-a7f38d9a51de |
| project_id              | f70a8b7d3aa047bc8a278a401186500a     |
| revision_number         | 0                                    |
| segment_id              | None                                 |
| service_types           |                                      |
| subnetpool_id           | None                                 |
| tags                    |                                      |
| updated_at              | 2020-08-13T11:31:24Z                 |
| use_default_subnet_pool | None                                 |
+-------------------------+--------------------------------------+


[root@controller-0 ~]# openstack image list
+--------------------------------------+---------------------+--------+
| ID                                   | Name                | Status |
+--------------------------------------+---------------------+--------+
| 48196a20-df86-4ace-8aef-9b17e65c3d76 | cirros-0.3.3-x86_64 | active |
+--------------------------------------+---------------------+--------+
[root@controller-0 ~]# openstack port create cf-port-162-168-168-1 --fixed-ip subnet=b582cb4b-9c75-4aa3-afe1-af7a93a64f77,ip-address=162.168.168.1 --network ac3941d0-eb7c-4f95-9e58-9c7dd7babafa
+-----------------------+------------------------------------------------------------------------------+
| Field                 | Value                                                                        |
+-----------------------+------------------------------------------------------------------------------+
| admin_state_up        | UP                                                                           |
| allowed_address_pairs |                                                                              |
| binding_host_id       |                                                                              |
| binding_profile       |                                                                              |
| binding_vif_details   |                                                                              |
| binding_vif_type      | unbound                                                                      |
| binding_vnic_type     | normal                                                                       |
| created_at            | 2020-08-13T03:17:52Z                                                         |
| data_plane_status     | None                                                                         |
| description           |                                                                              |
| device_id             |                                                                              |
| device_owner          |                                                                              |
| dns_assignment        | None                                                                         |
| dns_name              | None                                                                         |
| extra_dhcp_opts       |                                                                              |
| fixed_ips             | ip_address='162.168.168.1', subnet_id='b582cb4b-9c75-4aa3-afe1-af7a93a64f77' |
| id                    | fcf74cd0-c049-4a51-9846-78de3fe3cdf0                                         |
| ip_address            | None                                                                         |
| mac_address           | fa:16:3e:ee:c5:99                                                            |
| name                  | cf-port-162-168-168-1                                                        |
| network_id            | ac3941d0-eb7c-4f95-9e58-9c7dd7babafa                                         |
| option_name           | None                                                                         |
| option_value          | None                                                                         |
| port_security_enabled | True                                                                         |
| project_id            | f70a8b7d3aa047bc8a278a401186500a                                             |
| qos_policy_id         | None                                                                         |
| revision_number       | 3                                                                            |
| security_group_ids    | d3297c9a-44aa-4ae6-a3d2-78d29aa4ac5c                                         |
| status                | DOWN                                                                         |
| subnet_id             | None                                                                         |
| tags                  |                                                                              |
| trunk_details         | None                                                                         |
| updated_at            | 2020-08-13T03:17:52Z                                                         |
+-----------------------+------------------------------------------------------------------------------+


[root@controller-0 ~]# openstack port create cf-port-152-168-168-1 --fixed-ip subnet=ca02049b-af70-4538-8d8f-643c0418d5c6,ip-address=152.168.168.1 --network d91beeb4-312c-4e3e-8c6f-a7f38d9a51de
+-----------------------+------------------------------------------------------------------------------+
| Field                 | Value                                                                        |
+-----------------------+------------------------------------------------------------------------------+
| admin_state_up        | UP                                                                           |
| allowed_address_pairs |                                                                              |
| binding_host_id       |                                                                              |
| binding_profile       |                                                                              |
| binding_vif_details   |                                                                              |
| binding_vif_type      | unbound                                                                      |
| binding_vnic_type     | normal                                                                       |
| created_at            | 2020-08-13T11:41:29Z                                                         |
| data_plane_status     | None                                                                         |
| description           |                                                                              |
| device_id             |                                                                              |
| device_owner          |                                                                              |
| dns_assignment        | None                                                                         |
| dns_name              | None                                                                         |
| extra_dhcp_opts       |                                                                              |
| fixed_ips             | ip_address='152.168.168.1', subnet_id='ca02049b-af70-4538-8d8f-643c0418d5c6' |
| id                    | 6b85f1c6-2b9c-4847-bd11-f55ef4f052ee                                         |
| ip_address            | None                                                                         |
| mac_address           | fa:16:3e:23:40:78                                                            |
| name                  | cf-port-152-168-168-1                                                        |
| network_id            | d91beeb4-312c-4e3e-8c6f-a7f38d9a51de                                         |
| option_name           | None                                                                         |
| option_value          | None                                                                         |
| port_security_enabled | True                                                                         |
| project_id            | f70a8b7d3aa047bc8a278a401186500a                                             |
| qos_policy_id         | None                                                                         |
| revision_number       | 3                                                                            |
| security_group_ids    | d3297c9a-44aa-4ae6-a3d2-78d29aa4ac5c                                         |
| status                | DOWN                                                                         |
| subnet_id             | None                                                                         |
| tags                  |                                                                              |
| trunk_details         | None                                                                         |
| updated_at            | 2020-08-13T11:41:29Z                                                         |
+-----------------------+------------------------------------------------------------------------------+


[root@controller-0 ~]# openstack flavor create --id cf2G10G2VCPU --swap 2048 --disk 10 --vcpus 2 cf2G10G2VCPU
+----------------------------+--------------+
| Field                      | Value        |
+----------------------------+--------------+
| OS-FLV-DISABLED:disabled   | False        |
| OS-FLV-EXT-DATA:ephemeral  | 0            |
| disk                       | 10           |
| id                         | cf2G10G2VCPU |
| name                       | cf2G10G2VCPU |
| os-flavor-access:is_public | True         |
| properties                 |              |
| ram                        | 256          |
| rxtx_factor                | 1.0          |
| swap                       | 2048         |
| vcpus                      | 2            |
+----------------------------+--------------+

[root@controller-0 ~]# openstack server create --port fcf74cd0-c049-4a51-9846-78de3fe3cdf0 --image 48196a20-df86-4ace-8aef-9b17e65c3d76 --flavor cf2G10G2VCPU cf-vm-1
+-------------------------------------+------------------------------------------------------------+
| Field                               | Value                                                      |
+-------------------------------------+------------------------------------------------------------+
| OS-DCF:diskConfig                   | MANUAL                                                     |
| OS-EXT-AZ:availability_zone         |                                                            |
| OS-EXT-SRV-ATTR:host                | None                                                       |
| OS-EXT-SRV-ATTR:hypervisor_hostname | None                                                       |
| OS-EXT-SRV-ATTR:instance_name       |                                                            |
| OS-EXT-STS:power_state              | NOSTATE                                                    |
| OS-EXT-STS:task_state               | scheduling                                                 |
| OS-EXT-STS:vm_state                 | building                                                   |
| OS-SRV-USG:launched_at              | None                                                       |
| OS-SRV-USG:terminated_at            | None                                                       |
| accessIPv4                          |                                                            |
| accessIPv6                          |                                                            |
| addresses                           |                                                            |
| adminPass                           | kaJwR3pycvAy                                               |
| config_drive                        |                                                            |
| created                             | 2020-08-13T03:24:48Z                                       |
| flavor                              | cf2G10G2VCPU (cf2G10G2VCPU)                                |
| hostId                              |                                                            |
| id                                  | 5c7b64d1-4bd5-4c38-b3d0-5255c977dc9c                       |
| image                               | cirros-0.3.3-x86_64 (48196a20-df86-4ace-8aef-9b17e65c3d76) |
| key_name                            | None                                                       |
| name                                | cf-vm-1                                                    |
| progress                            | 0                                                          |
| project_id                          | f70a8b7d3aa047bc8a278a401186500a                           |
| properties                          |                                                            |
| security_groups                     | name='default'                                             |
| status                              | BUILD                                                      |
| updated                             | 2020-08-13T03:24:48Z                                       |
| user_id                             | 277972b4f2284fa386f6475babfbda9a                           |
| volumes_attached                    |                                                            |
+-------------------------------------+------------------------------------------------------------+

[root@controller-0 ~]# openstack flavor create --id cf2G1G2VCPU --swap 2048 --disk 1 --vcpus 2 cf2G1G2VCPU
+----------------------------+-------------+
| Field                      | Value       |
+----------------------------+-------------+
| OS-FLV-DISABLED:disabled   | False       |
| OS-FLV-EXT-DATA:ephemeral  | 0           |
| disk                       | 1           |
| id                         | cf2G1G2VCPU |
| name                       | cf2G1G2VCPU |
| os-flavor-access:is_public | True        |
| properties                 |             |
| ram                        | 256         |
| rxtx_factor                | 1.0         |
| swap                       | 2048        |
| vcpus                      | 2           |
+----------------------------+-------------+


glance image-create --name nfvt2019.qcow2 --file nfvt2019.qcow2 --disk-format qcow2 --container-format bare --visibility public --progress

[root@controller-0 ~]# glance image-create --name nfvt2019.qcow2 --file nfvt2019.qcow2 --disk-format qcow2 --container-format bare --visibility public --progress
[=============================>] 100%
+------------------+--------------------------------------+
| Property         | Value                                |
+------------------+--------------------------------------+
| checksum         | 5e20b49411fa590befd4d6fc8ba18879     |
| container_format | bare                                 |
| created_at       | 2020-08-13T07:15:49Z                 |
| disk_format      | qcow2                                |
| id               | 89c2442a-9948-476f-8f55-14a368a7d96f |
| min_disk         | 0                                    |
| min_ram          | 0                                    |
| name             | nfvt2019.qcow2                       |
| owner            | f70a8b7d3aa047bc8a278a401186500a     |
| protected        | False                                |
| size             | 628817920                            |
| status           | active                               |
| tags             | []                                   |
| updated_at       | 2020-08-13T07:15:52Z                 |
| virtual_size     | None                                 |
| visibility       | public                               |
+------------------+--------------------------------------+

[root@controller-0 ~]# glance image-create --name cirros-0-4 --file cirros-0.4.0-x86_64-disk.img --disk-format qcow2 --container-format bare --visibility public --progress
[=============================>] 100%
+------------------+--------------------------------------+
| Property         | Value                                |
+------------------+--------------------------------------+
| checksum         | 443b7623e27ecf03dc9e01ee93f67afe     |
| container_format | bare                                 |
| created_at       | 2020-08-13T07:24:53Z                 |
| disk_format      | qcow2                                |
| id               | 54503f8b-749d-4fe9-9a05-00082d81c25d |
| min_disk         | 0                                    |
| min_ram          | 0                                    |
| name             | cirros-0-4                           |
| owner            | f70a8b7d3aa047bc8a278a401186500a     |
| protected        | False                                |
| size             | 12716032                             |
| status           | active                               |
| tags             | []                                   |
| updated_at       | 2020-08-13T07:24:53Z                 |
| virtual_size     | None                                 |
| visibility       | public                               |
+------------------+--------------------------------------+


openstack server create --port fcf74cd0-c049-4a51-9846-78de3fe3cdf0 --image 54503f8b-749d-4fe9-9a05-00082d81c25d --flavor cf2G1G2VCPU cf-vm-1
```



### linuxbridge切换成ovs agent

#### 配置ml2

##### 修改/etc/neutron/plugins/ml2/ml2_conf.ini文件

* 网络和计算节点都修改，计算节点没有这个配置文件拷贝过去

```shell
#mechanism_drivers openvswitch
VALUE="openvswitch,l2population"; FILE=/etc/neutron/plugins/ml2/ml2_conf.ini; KEY="mechanism_drivers"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

```



#### 配置ovs agent

##### 修改/etc/neutron/plugins/ml2/openvswitch_agent.ini

```shell
#agent
VALUE="tunnel_types=vxlan\nl2_population=True\nprevent_arp_spoofing=True; FILE=/etc/neutron/plugins/ml2/openvswitch_agent.ini; KEY="\[agent\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

# local_ip根据控制和计算节点的不同进行修改
#local_ip
VALUE="192.168.8.201"; FILE=/etc/neutron/plugins/ml2/openvswitch_agent.ini; KEY="local_ip"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#bridge_mappings
VALUE="service:br-ex"; FILE=/etc/neutron/plugins/ml2/openvswitch_agent.ini; KEY="bridge_mappings"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#firewall_driver
VALUE="iptables_hybrid"; FILE=/etc/neutron/plugins/ml2/openvswitch_agent.ini; KEY="firewall_driver"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

#enable_security_group
VALUE="True"; FILE=/etc/neutron/plugins/ml2/openvswitch_agent.ini; KEY="enable_security_group"; NEW_VALUE="$KEY=$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```



#### 配置l3_agent.ini

* /etc/neutron/l3_agent.ini

```shell
#interface_driver ovs
VALUE="neutron.agent.linux.interface.OVSInterfaceDriver"; FILE=/etc/neutron/l3_agent.ini; KEY="interface_driver"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi

```



#### 配置vpn_agent

##### 修改/etc/neutron/vpn_agent.ini网络节点

```shell
#interface_driver ovs
VALUE="interface_driver = neutron.agent.linux.interface.OVSInterfaceDriver"; FILE=/etc/neutron/vpn_agent.ini; KEY="[DEFAULT]"; GREP_KEY="\[DEFAULT\]";  NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$GREP_KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo -e "$NEW_VALUE" >> $FILE; fi

```



#### 配置DHCP Agent

##### 修改/etc/neutron/dhcp_agent.ini

```shell
#interface_driver 
# ovs
VALUE="neutron.agent.linux.interface.OVSInterfaceDriver"; FILE=/etc/neutron/dhcp_agent.ini; KEY="interface_driver"; NEW_VALUE="$KEY = $VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```



## FAQ

### nova服务报503



```note
If the nova-compute service fails to start, check /var/log/nova/nova-compute.log. The error message AMQP server on controller:5672 is unreachable likely indicates that the firewall on the controller node is preventing access to port 5672. Configure the firewall to open port 5672 on the controller node and restart nova-compute service on the compute node.
```

```note
[root@controller-0 ~]# openstack compute service list --service nova-compute
The server is currently unavailable. Please try again at a later time.<br /><br />

 (HTTP 503) (Request-ID: req-59639c3c-b346-46a2-82fe-baa07ea1d2fc)
```

* 就是修改nova 的密码为配置文件中的nova密码

```shell
# 503问题就是修改nova 的密码为配置文件中的nova密码
openstack user set --password nova nova
openstack user set --password demo demo
openstack user set --password glance glance
openstack user set --password neutron neutron
openstack user set --password placement placement
```



### 数据库连接数太多

```note
OperationalError: (pymysql.err.OperationalError) (1040, u'Too many connections')
```

#### 配置/etc/my.cnf文件

* /etc/my.cnf 文件在  [mysqld]  标签下添加
max_connections=4096

```shell

VALUE="max_connections=4096"; FILE=/etc/my.cnf; KEY="\[mysqld\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE ;if [ -n "$LINE" ]; then sed -i "${LINE}s/.*/$NEW_VALUE/" $FILE; else echo -e "$KEY\n$VALUE" >> $FILE; fi
```



#### 配置mysql最大文件描述符限制

*  解决mysql 最大连接数 214 问题

    在文件[Service]下添加:

    LimitNOFILE=65535
    LimitNPROC=65535

```shell
KEY="\[Service\]"; VALUE="LimitNOFILE=65535\nLimitNPROC=65535"; NEW_VALUE="$KEY\n$VALUE" FILE=/usr/lib/systemd/system/mariadb.service; LINE=$(grep "^$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE ;if [ -n "$LINE" ]; then sed -i "${LINE}s/.*/$NEW_VALUE/" $FILE; else echo -e "$KEY\n$VALUE" >> $FILE; fi
```



#### 重启mysql服务

```shell
systemctl daemon-reload
systemctl restart  mariadb.service
```



### 安装openstack-nova-compute组件kvm依赖报错

```note
CentOS 安装openstack-nova-compute组件，报错Requires: qemu-kvm-rhev >= 2.9.0

```

* 解决方式添加kvm的repo源即可

```shell
# 配置nova依赖的kvm的源
tee /etc/yum.repos.d/CentOS-kvm.repo << EOF
[Virt]
name=CentOS- - Base
#mirrorlist=http://mirrorlist.centos.org/?release=&arch=&repo=os&infra=
baseurl=http://mirrors.sohu.com/centos/7/virt/x86_64/kvm-common/
#baseurl=http://mirror.centos.org/centos//os//
gpgcheck=0
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7
EOF

```



### neutron-server安装了vpn启动报错导包错误

```log
ERROR neutron ImportError: No module named vpn.service_drivers.ipsec
```



* 修改/etc/neutron/neutron_vpnaas.conf中的service_provider即可

```shell
# [service_providers] service_provider
VALUE="service_provider = VPN:libreswan:neutron_vpnaas.services.vpn.service_drivers.ipsec.IPsecVPNDriver:default"; FILE=/etc/neutron/neutron_vpnaas.conf; KEY="\[service_providers\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "^$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```





### neutron-server安装了vpn启动报错缺少表字段

```log
2020-08-20 02:20:13.421 88450 ERROR neutron DBError: (pymysql.err.InternalError) (1054, u"Unknown column 'vpnservices.project_id' in 'field list'") [SQL: u'SELECT vpnservices.project_id AS vpnservices_project_id, vpnservices.id AS vpnservices_id, vpnservices.name AS vpnservices_name, vpnservices.description AS vpnservices_description, vpnservices.status AS vpnservices_status, vpnservices.admin_state_up AS vpnservices_admin_state_up, vpnservices.external_v4_ip AS vpnservices_external_v4_ip, vpnservices.external_v6_ip AS vpnservices_external_v6_ip, vpnservices.subnet_id AS vpnservices_subnet_id, vpnservices.router_id AS vpnservices_router_id, vpnservices.flavor_id AS vpnservices_flavor_id \nFROM vpnservices']

```



* 执行以下命令即可

```shell
su -s /bin/sh -c "neutron-db-manage --config-file /etc/neutron/neutron.conf --config-file /etc/neutron/vpn_agent.ini --config-file /etc/neutron/neutron_vpnaas.conf upgrade head" neutron
```



### neutron-server安装了vpn启动报错providers不是唯一的



```log
 Invalid: Driver neutron_vpnaas.services.vpn.service_drivers.ipsec.IPsecVPNDriver is not unique across providers

```



* 删除多余的service_providers

```shell
# 删除多余的service_providers
VALUE=""; FILE=/etc/neutron/neutron_vpnaas.conf; KEY="service_provider"; NEW_VALUE="$KEY $VALUE"; LINE=$(grep "$KEY" -w -n -m2 $FILE | awk '{if (NR==1) print$0}' | awk -F ':' '{print$1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}d" $FILE;fi

```



### OpenStack 启动虚拟机 Booting from Hard Disk

* 修改/etc/nova/nova.conf文件

```shell
# [libvirt] cpu_mode = none virt_type = qemu
VALUE="cpu_mode = none\nvirt_type = qemu"; FILE=/etc/nova/nova.conf; KEY="\[libvirt\]"; NEW_VALUE="$KEY\n$VALUE"; LINE=$(grep "^$KEY" -w -n -m1 $FILE | awk -F ':' '{print $1}'); echo $LINE; if [ -n "$LINE" ]; then sed -i "${LINE}s|.*|$NEW_VALUE|" $FILE; else echo "$NEW_VALUE" >> $FILE; fi
```



* 重启nova服务

```shell
# 控制
systemctl restart openstack-nova-api.service
systemctl restart openstack-nova-consoleauth.service 
systemctl restart openstack-nova-scheduler.service
systemctl restart openstack-nova-conductor.service
systemctl restart openstack-nova-novncproxy.service


# 计算
systemctl enable libvirtd.service openstack-nova-compute.service
systemctl restart libvirtd.service openstack-nova-compute.service
systemctl status libvirtd.service openstack-nova-compute.service
```



### n

```note

```



```shell
tee /etc/hostname << EOF
controller-0
EOF

tee /etc/hostname << EOF
compute-0
EOF

neutron agent-list
neutron agent-delete 095c6e18-60eb-4c3f-a721-bb6d99e098ba 2f64f641-73d6-49fc-ab8f-a871b851fab4
neutron agent-list
systemctl  restart  neutron-openvswitch-agent

```

