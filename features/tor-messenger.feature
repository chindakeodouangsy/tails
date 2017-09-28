@product
Feature: Chatting anonymously using Tor Messenger

  Scenario: Start Tor Messenger
    Given I have started Tails from DVD without network and logged in
    When I start "Tor Messenger" via GNOME Activities Overview
    Then Tor Messenger seems to start