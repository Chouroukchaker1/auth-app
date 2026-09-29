package com.example.authjwt.user;

import static org.junit.jupiter.api.Assertions.assertAll;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class UserTest {
    @Test
    void newUserKeepsProvidedDetailsAndStartsWithVerifiedEmail() {
        User user = new User("Chourouk Chaker", "chourouk@example.com", "secret", "USER");

        assertAll(
                () -> assertEquals("Chourouk Chaker", user.getFullName()),
                () -> assertEquals("chourouk@example.com", user.getEmail()),
                () -> assertEquals("secret", user.getPassword()),
                () -> assertEquals("USER", user.getRole()),
                () -> assertTrue(user.isEmailVerified())
        );
    }
}