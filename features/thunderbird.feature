#11465
@product @check_tor_leaks
Feature: Thunderbird email client
  As a Tails user
  I may want to use an email client

  Background:
    Given I have started Tails from DVD and logged in and the network is connected
    And I have not configured an email account
    When I start Thunderbird
    Then I am prompted to setup an email account

  Scenario: Only the expected addons are installed
    Given I cancel setting up an email account
    When I open Thunderbird's Add-ons Manager
    And I click the extensions tab
    Then I see that only the Enigmail and TorBirdy addons are enabled in Thunderbird

  Scenario: Torbirdy is configured to use Tor
    Given I cancel setting up an email account
    Then I see that Torbirdy is configured to use Tor

  #11890
  @fragile
  Scenario: Thunderbird's autoconfiguration wizard
    When I enter tails@riseup.net into the autoconfiguration wizard
    Then I see the "Configuration found on Thunderbird installation" label
    And the autoconfiguration wizard's choice for the incoming server is secure IMAP
    When I select the autoconfiguration wizard's POP3 choice
    Then the autoconfiguration wizard's choice for the incoming server is secure POP3
    And the autoconfiguration wizard's choice for the outgoing server is secure SMTP

  #11890
  @fragile
  Scenario: Thunderbird's autoconfiguration wizard
    When I enter tails@boum.org into the autoconfiguration wizard
    Then I see the "Configuration found at email provider" label
    And the autoconfiguration wizard's choice for the incoming server is secure IMAP
    When I select the autoconfiguration wizard's POP3 choice
    Then the autoconfiguration wizard's choice for the incoming server is secure POP3
    And the autoconfiguration wizard's choice for the outgoing server is secure SMTP

  #11890
  @fragile
  Scenario: Thunderbird's autoconfiguration wizard
    When I enter tails@gmail.com into the autoconfiguration wizard
    Then I see the "Configuration found in Mozilla ISP database" label
    And the autoconfiguration wizard's choice for the incoming server is secure IMAP
    And the autoconfiguration wizard's choice for the outgoing server is secure SMTP
    When I click the "Manual config" button
    Then I do not see any "OAuth2" menu item
    But I see 2 "Normal password" menu items
    When I enter tails@gmail.com into the autoconfiguration wizard
    Then I see the "Configuration found in Mozilla ISP database" label
    And I select the autoconfiguration wizard's POP3 choice
    And the autoconfiguration wizard's choice for the incoming server is secure POP3
    And the autoconfiguration wizard's choice for the outgoing server is secure SMTP
    When I click the "Manual config" button
    Then I do not see any "OAuth2" menu item
    But I see 2 "Normal password" menu items

  #11890
  @fragile
  Scenario: Thunderbird's autoconfiguration wizard
    When I enter tails@herbesfolles.org into the autoconfiguration wizard
    Then I see the "Configuration found by trying common server names" label
    And the autoconfiguration wizard's choice for the incoming server is secure IMAP
    When I select the autoconfiguration wizard's POP3 choice
    Then the autoconfiguration wizard's choice for the incoming server is secure POP3
    Then the autoconfiguration wizard's choice for the outgoing server is secure SMTP

  #11890
  @fragile
  Scenario: Thunderbird can send emails, and receive emails over IMAP
    When I enter my email credentials into the autoconfiguration wizard
    Then the autoconfiguration wizard's choice for the incoming server is secure IMAP
    When I accept the autoconfiguration wizard's configuration
    And I send an email to myself
    And I fetch my email
    Then I can find the email I sent to myself in my inbox

  #11890
  @fragile
  Scenario: Thunderbird can download the inbox with POP3
    When I enter my email credentials into the autoconfiguration wizard
    Then the autoconfiguration wizard's choice for the incoming server is secure IMAP
    When I select the autoconfiguration wizard's POP3 choice
    Then the autoconfiguration wizard's choice for the incoming server is secure POP3
    When I accept the autoconfiguration wizard's configuration
    And I fetch my email
    Then my Thunderbird inbox is non-empty
