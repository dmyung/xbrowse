class postgresql {
    
    package { 'postgresql93-libs': ensure => latest }
    package { 'postgresql93-devel': ensure => latest }

    class { 'postgresql::globals':
        encoding => 'UTF8',
        manage_package_repo => true,
    }

    class { 'postgresql::server':
            listen_addresses => '*',
            postgres_password => 'postgrespassword',
            require => Class[ 'globals' ],
    }

    class { 'postgresql::server::contrib':
        package_ensure => 'present',
    }

    postgresql::server::db { 'xbrowsedb':
        user     => 'xbrowseuser',
        password => postgresql_password('xbrowseuser', 'password'),
    }

}
