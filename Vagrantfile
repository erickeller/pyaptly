# -*- mode: ruby -*-
# vi: set ft=ruby :

# All Vagrant configuration is done below. The "2" in Vagrant.configure
# configures the configuration version (we support older styles for
# backwards compatibility). Please don't change it unless you know what
# you're doing.
Vagrant.configure(2) do |config|
  # The most common configuration options are documented and commented below.
  # For a complete reference, please see the online documentation at
  # https://docs.vagrantup.com.

  # Every Vagrant development environment requires a box. You can search for
  # boxes at https://atlas.hashicorp.com/search.
  config.vm.box = "adsy-centos-6.5.box"
  config.vm.box_url = "https://pkg.adfinis-sygroup.ch/vagrant/adsy-centos-6.5.box"
  config.vm.box_download_checksum = "a0f2cc25560495cd927da103659a59d69b2e4f1bf032ee67f35e8ea1b1c88a80"
  config.vm.box_download_checksum_type = "sha256"
  begin
    if Vagrant.plugin("2").manager.config.has_key? :vbguest then
      config.vbguest.auto_update = false
    end
  rescue
  end
  if ! File.exists?(".vagrant/machines/default/virtualbox/id")
    # Then this machine is brannd new.
    system "rm -rf pyaptly.egg-info/"
  end

  config.ssh.forward_agent = true

  # Disable automatic box update checking. If you disable this, then
  # boxes will only be checked for updates when the user runs
  # `vagrant box outdated`. This is not recommended.
  # config.vm.box_check_update = false

  # Create a forwarded port mapping which allows access to a specific port
  # within the machine from a port on the host machine. In the example below,
  # accessing "localhost:8080" will access port 80 on the guest machine.
  # config.vm.network "forwarded_port", guest: 80, host: 8080

  # Create a private network, which allows host-only access to the machine
  # using a specific IP.
  # config.vm.network "private_network", ip: "192.168.33.10"

  # Create a public network, which generally matched to bridged network.
  # Bridged networks make the machine appear as another physical device on
  # your network.
  # config.vm.network "public_network"

  # Share an additional folder to the guest VM. The first argument is
  # the path on the host to the actual folder. The second argument is
  # the path on the guest to mount the folder. And the optional third
  # argument is a set of non-required options.
  # config.vm.synced_folder "../data", "/vagrant_data"

  # Provider-specific configuration so you can fine-tune various
  # backing providers for Vagrant. These expose provider-specific options.
  # Example for VirtualBox:
  #
  config.vm.provider "virtualbox" do |vb|
    # Display the VirtualBox GUI when booting the machine
    # vb.gui = true
  
    # Customize the amount of memory on the VM:
    vb.memory = "512"
	vb.customize ["modifyvm", :id, "--natdnshostresolver1", "on"]
  end
  #
  # View the documentation for the provider you are using for more
  # information on available options.

  # Define a Vagrant Push strategy for pushing to Atlas. Other push strategies
  # such as FTP and Heroku are also available. See the documentation at
  # https://docs.vagrantup.com/v2/push/atlas.html for more information.
  # config.push.define "atlas" do |push|
  #   push.app = "YOUR_ATLAS_USERNAME/YOUR_APPLICATION_NAME"
  # end

  # Enable provisioning with a shell script. Additional provisioners such as
  # Puppet, Chef, Ansible, Salt, and Docker are also available. Please see the
  # documentation for more information about their specific syntax and use.
  config.vm.provision "shell", inline: <<-SHELL
    set -e
    yum -y install wget rsync
    cd /usr/local/bin
    wget -q https://dl.bintray.com/smira/aptly/0.9.5/centos-6.5-x64/aptly
    sha256sum -c <<EOF
9f36902eab9994bce32356dc22d2317f0939b899591f3262379a9af1301ad1da  aptly
EOF
    if [ "$?" = "0" ]; then
      chmod 755 aptly
    else
      rm aptly
    fi
    set +e
    gpg --import < /vagrant/vagrant/key.pub
    gpg --import < /vagrant/vagrant/key.sec
    gpg --batch --no-default-keyring --keyring trustedkeys.gpg --import < /vagrant/vagrant/key.pub
    sudo -u vagrant gpg --import < /vagrant/vagrant/key.pub
    sudo -u vagrant gpg --import < /vagrant/vagrant/key.sec
    sudo -u vagrant gpg --batch --no-default-keyring --keyring trustedkeys.gpg --import < /vagrant/vagrant/key.pub
    set -e
    cd /vagrant/vagrant/libfaketime
    make install
    /usr/local/bin/aptly repo create -architectures="amd64" fakerepo01
    /usr/local/bin/aptly repo add fakerepo01 /vagrant/vagrant/*.deb
    /usr/local/bin/aptly repo create -architectures="amd64" fakerepo02
    /usr/local/bin/aptly repo add fakerepo02 /vagrant/vagrant/*.deb
    /usr/local/bin/aptly publish repo -gpg-key="650FE755" -distribution="main" fakerepo01 fakerepo01
    /usr/local/bin/aptly publish repo -gpg-key="650FE755" -distribution="main" fakerepo02 fakerepo02
    yum -y install epel-release
    yum -y install nginx
    cp /vagrant/vagrant/nginx.conf /etc/nginx/nginx.conf
    cp /vagrant/vagrant/default.conf /etc/nginx/conf.d/default.conf
    service nginx restart
    chkconfig nginx on
    python /vagrant/vagrant/get-pip.py
    pip install virtualenv
    pip install ipython==1.2.1
    pip install ipdb
    sudo -u vagrant virtualenv /home/vagrant/.venv
    sudo -u vagrant bash -c "echo '. /home/vagrant/.venv/bin/activate' >> /home/vagrant/.bashrc"
    true
  SHELL
end
