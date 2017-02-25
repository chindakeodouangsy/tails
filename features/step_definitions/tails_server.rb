def tails_server_app
  Dogtail::Application.new('tails-server')
end

def tails_server_main
  tails_server_app.child('Tails Server', roleName: 'frame')
end

def outer_box
  tails_server_main.child(roleName: 'filler', recursive: false)
end

def service_outer_box
  outer_box.child(roleName: 'filler', recursive: false)
end

def service_listbox
  service_scrolledwindow = service_outer_box.child(roleName: 'scroll pane', recursive: false)
  service_viewport = service_scrolledwindow.child(roleName: 'viewport', recursive: false)
  service_viewport.child(roleName: 'list box', recursive: false)
end

def service_toolbar
  service_outer_box.child(roleName: 'tool bar', recursive: false)
end

def options_grid
  service_config_scrolledwindow = outer_box.child(roleName: 'scroll pane', recursive: false)
  service_config_viewport = service_config_scrolledwindow.child(roleName: 'viewport', recursive: false) 
  service_config_outer_box = service_config_viewport.child(roleName: 'filler', recursive: false)
  service_config_outer_box.child(roleName: 'panel', recursive: false)
end

def add_service_window
  tails_server_app.child('Add Service', roleName: 'frame')
end

def add_service_listbox
  add_service_window.child(roleName: 'panel', recursive: false).child(roleName: 'list box', recursive: false)
end

def add_service_list_item(service)
  add_service_listbox.children(recursive: false).each do |listitem|
    if not listitem.children(name: service, roleName: 'label').empty?
      return listitem
    end
  end
  $stderr.puts "Could not find service '#{service}'"
end


def client_app
  Dogtail::Application.new('tails-server-client')
end

def client_app_textview
  client_app.child(roleName: 'frame', recursive: false).
    child(roleName: 'filler', recursive: false).
    child(roleName: 'text', recursive: false)
end


When /^I start Tails Server and enter the sudo password$/ do
  step 'I start "Tails Server" via the GNOME "Internet" applications menu'
  step 'I enter the sudo password in the gksudo prompt'
  tails_server_app.wait(60)
end

Then /^I see ([^"]+) in the service list$/ do |service|
  if service == "no services"
    service_rows = service_listbox.children(roleName: 'list item', recursive: false)
    assert_equal(0, service_rows.size)
  else
    service_listbox.child(name: service, roleName: 'label').exist?()
  end
end

When /^I add ([^"]+) service in Tails Server$/ do |service|
  service_toolbar.child('Add').click()
  add_service_list_item(service).click()
end

Then /the service is stopped$/ do
  options_grid.child(name: 'Stopped').exist?
end

When /^I start the service$/ do
  options_grid.child(roleName: 'toggle button', action: 'toggle').click()
end

Then /^the service starts successfully$/ do
  options_grid.child(name: 'Online').wait(1200)
end

When /^I copy the connection information to the clipboard$/ do
  options_grid.child(name: 'Connection Info').click()
  # XXX: Continue
end

When /^I start the client app$/ do
  $vm.execute("QT_ACCESSIBILITY=1")
  $vm.execute("tails-server-client")
end

When /^I paste the clipboard in the client app and click connect$/ do
  client_app_textview.typeText($vm.get_clipboard)
  sleep(2)  # Give the client app some time to process the pasted data
  client_app.child(name: 'Connect').click()
end

Then /^The Mumble client starts and connects$/ do
  # XXX
end

