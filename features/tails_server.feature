@product @check_tor_leaks
Feature: Tails Server
  As a Tails user
  when using Tails Server
  I should be able to install services
  # And I should be able to start services
  # And I should be able to connect to services
  # And I should be able to configure services
  # And I should be able to stop services
  # And I should be able to uninstall services
  # And I should be able to persist the services' data and configuration
  # And all traffic should flow only through Tor

  Background:  
    # Given I have started Tails from DVD without network and logged in with an administration password
    Given I have started Tails from DVD and the network is connected
    And I configure APT to use non-onion sources

  Scenario: Installing a service
    When I start Tails Server
    Then I see no services in the service list
    When I add Mumble service in Tails Server
    Then I see Mumble in the service list
    And the service is stopped
    When I start the service
    Then the service starts successfully
