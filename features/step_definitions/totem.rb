Given /^I create sample videos$/ do
  @video_dir_on_host = "#{$config["TMPDIR"]}/video_dir"
  FileUtils.mkdir_p(@video_dir_on_host)
  add_after_scenario_hook { FileUtils.rm_r(@video_dir_on_host) }
  fatal_system("avconv -loop 1 -t 30 -f image2 " +
               "-i 'features/images/USBTailsLogo.png' " +
               "-an -vcodec libx264 -y " +
               '-filter:v "crop=in_w-mod(in_w\,2):in_h-mod(in_h\,2)" ' +
               "'#{@video_dir_on_host}/video.mp4' >/dev/null 2>&1")
end

Given /^I plug and mount a USB drive containing sample videos$/ do
  @video_dir_on_guest = share_host_files(
    Dir.glob("#{@video_dir_on_host}/*")
  )
end

Given /^I copy the sample videos to "([^"]+)" as user "([^"]+)"$/ do |destination, user|
  for video_on_host in Dir.glob("#{@video_dir_on_host}/*.mp4") do
    video_name = File.basename(video_on_host)
    src_on_guest = "#{@video_dir_on_guest}/#{video_name}"
    dst_on_guest = "#{destination}/#{video_name}"
    step "I copy \"#{src_on_guest}\" to \"#{dst_on_guest}\" as user \"amnesia\""
  end
end

When /^I(?:| try to) open "([^"]+)" with Totem$/ do |filename|
  step "I run \"totem #{filename}\" in GNOME Terminal"
end

When /^I close Totem$/ do
  step 'I kill the process "totem"'
end

When /^I add "([^"]+)" as a local video in Totem$/ do |filename|
  totem = Dogtail::Application.new('totem')
  totem_main = totem.child('Videos', roleName: 'frame')
  totem_main.child('Menu', roleName: 'toggle button').click
  # Dogtail has a unicode issue in it's logging machinery (against the
  # "...", which actually is the unicode character for "Three dots",
  # so we avoid the logging by playing with coordinates instead. I
  # believe this will be fixed once we run Dogtail >= 1.0 under Python3.
  x, y = totem_main.child('Add Local Video...', roleName: 'push button').position
  @screen.click_point(x, y)
  totem_file_chooser = totem.child('Add Videos', roleName: 'file chooser')
  totem_file_chooser.child('Enter Location', roleName: 'table cell').click()
  totem_file_chooser.child('Location:', roleName: 'label')
    .parent.child(roleName: 'text').text = filename
  totem_file_chooser.child('Add', roleName: 'push button').click()
end

Then /^"([^"]+)" is added as a local video in Totem$/ do |filename|
  totem = Dogtail::Application.new('totem')
  totem_file_chooser = totem.child('Add Videos', roleName: 'file chooser')
  name = File.basename(filename).sub(/\.[^.]+$/, '')
  # Some elements of role 'icon' seem to set the `showing` attribute
  # incorrectly, including the one we are looking for.
  video = totem.children(roleName: 'icon', showingOnly: false).find do |n|
    begin
      n.text == name
    rescue
      false
    end
  end
  assert_not_nil(video)
end

Then /^I can watch a WebM video over HTTPs$/ do
  test_url = 'https://tails.boum.org/lib/test_suite/test.webm'
  recovery_on_failure = Proc.new do
    step 'I close Totem'
  end
  retry_tor(recovery_on_failure) do
    step "I open \"#{test_url}\" with Totem"
    @screen.wait("SampleRemoteWebMVideoFrame.png", 120)
  end
end
