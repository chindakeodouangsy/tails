When /^disable MAC spoofing in Tails Greeter$/ do
  next if @skip_steps_while_restoring_background
  @screen.wait_and_click("TailsGreeterMACSpoofing.png", 30)
end

Then /^the network device has (its default|a spoofed) MAC address configured$/ do |mode|
  next if @skip_steps_while_restoring_background
  is_spoofed = (mode == "a spoofed")
  nic = "eth0"
  nic_exists = @vm.execute(
    ". /usr/local/lib/tails-shell-library/hardware.sh && " +
    "nic_exists #{nic}"
  ).success?
  next if !nic_exists
  nic_real_mac = @vm.real_mac
  nic_current_mac = @vm.execute_successfully(
    ". /usr/local/lib/tails-shell-library/hardware.sh && " +
    "get_current_mac_of_nic #{nic}"
  ).stdout.chomp
  if is_spoofed
    if nic_real_mac == nic_current_mac
      save_pcap_file
      raise "The MAC address was expected to be spoofed but wasn't"
    end
  else
    if nic_real_mac != nic_current_mac
      save_pcap_file
      raise "The MAC address is spoofed but was expected to not be"
    end
  end
end

Then /^the real MAC address was (not )?leaked$/ do |mode|
  next if @skip_steps_while_restoring_background
  is_leaking = mode.nil?
  leaks = FirewallLeakCheck.new(@sniffer.pcap_file)
  mac_leaks = leaks.mac_leaks
  if is_leaking
    if !mac_leaks.include?(@vm.real_mac)
      save_pcap_file
      raise "The real MAC address was expected to leak but didn't. We " +
            "observed the following MAC addresses: #{mac_leaks}"
    end
  else
    if mac_leaks.include?(@vm.real_mac)
      save_pcap_file
      raise "The real MAC address was leaked but was expected not to. We " +
            "observed the following MAC addresses: #{mac_leaks}"
    end
  end
end

Given /^macchanger will fail by not spoofing and always returns ([\S]+)$/ do |mode|
  next if @skip_steps_while_restoring_background
  @vm.execute_successfully("mv /usr/bin/macchanger /usr/bin/macchanger.orig")
  @vm.execute_successfully("ln -s /bin/#{mode} /usr/bin/macchanger")
end

Given /^MAC spoofing will fail, and the module cannot be unloaded$/ do
  next if @skip_steps_while_restoring_background
  step "macchanger will fail by not spoofing and always returns true"
  @vm.execute_successfully("mv /sbin/rmmod /sbin/rmmod.orig")
  @vm.execute_successfully("ln -s /bin/false /sbin/rmmod")
end

When /^see the "Network card disabled" notification$/ do
  next if @skip_steps_while_restoring_background
  @screen.wait("MACSpoofNetworkCardDisabled.png", 60)
end

When /^see the "All networking disabled" notification$/ do
  next if @skip_steps_while_restoring_background
  @screen.wait("MACSpoofNetworkingDisabled.png", 60)
end

Then /^(\d+|no) network device(?:s)? (?:is|are) present$/ do |expected_nr_nics|
  next if @skip_steps_while_restoring_background
  # note that "no".to_i => 0 in Ruby.
  expected_nr_nics = expected_nr_nics.to_i
  nr_nics = @vm.execute_successfully(
    ". /usr/local/lib/tails-shell-library/hardware.sh && get_all_ethernet_nics"
  ).stdout.split.size
  assert_equal(expected_nr_nics, nr_nics)
end

Then /^networking was disabled$/ do
  next if @skip_steps_while_restoring_background
  nm_is_disabled = not(@vm.file_exist?("/etc/init.d/network-manager")) &&
                   not(@vm.file_exist?("/usr/sbin/NetworkManager"))
  assert(nm_is_disabled, "NetworkManager was not disabled")
  nic = "eth0"
  for addr_type in ["nic_ipv4_addr", "nic_ipv6_addr"] do
    addr = @vm.execute_successfully(
      ". /usr/local/lib/tails-shell-library/hardware.sh && " +
      "#{addr_type} #{nic}"
    ).stdout.chomp
    assert_equal("", addr, "NIC #{nic} was assigned address #{addr}")
  end
end
