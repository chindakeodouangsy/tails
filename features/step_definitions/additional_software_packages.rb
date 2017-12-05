When /^I configure additional software packages to install "(.+?)"$/ do |package|
  $vm.file_overwrite(
    '/live/persistence/TailsData_unlocked/live-additional-software.conf',
    package + "\n"
  )
end

Then /^the additional software package installation service is run$/ do
  try_for_success(timeout: 300) do
    $vm.file_exist?('/run/live-additional-software/installed')
  end
end
