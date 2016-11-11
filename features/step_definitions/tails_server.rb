def tails_server_app
  Dogtail::Application.new('tails-server')
end

def tails_server_main
  tails_server_app.child('Tails Server', roleName: 'frame')
end

When /^I start Tails Server and enter the sudo password$/ do
  step 'I start "Tails Server" via the GNOME "Internet" applications menu'
  step 'I enter the sudo password in the gksudo prompt'
  tails_server_main.wait(10)
end


