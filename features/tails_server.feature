@product
Feature: Tails Server
  As a Tails user
  when using Tails Server
  I should be able to install services
  And I should be able to start services
  And I should be able to connect to services
  And I should be able to configure services
  And I should be able to stop services
  And I should be able to uninstall services
  And I should be able to persist the services' data and configuration
  And all traffic should flow only through Tor

  Background:  
    Given I have started Tails from DVD and logged in with an administration password and the network is connected


  @check_tor_leaks
  Scenario: Installing a service
    When I start Tails Server and enter the sudo password
    # Then there are no services in the main window
    # When I add a Mumble service

    # Adding a service:
    #When I click the + button
    #Then I see the service chooser dialog
    
