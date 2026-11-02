package com.example.authjwt.member;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class MemberFileStorageTest {
    @TempDir
    Path directory;

    @Test
    void storesFilesUnderMemberReferenceAndReturnsRelativeKey() throws IOException {
        MemberFileStorage storage = new MemberFileStorage(directory.toString());
        byte[] content = {1, 2, 3};

        String key = storage.store("12345678", "photo", "portrait.png", content);

        assertTrue(key.startsWith("12345678/photo-"));
        assertTrue(key.endsWith(".png"));
        assertTrue(Files.isRegularFile(directory.resolve(key)));
        assertArrayEquals(content, storage.read(key));
    }

    @Test
    void rejectsKeysOutsideStorageDirectory() {
        MemberFileStorage storage = new MemberFileStorage(directory.toString());

        assertThrows(IOException.class, () -> storage.read("../outside.txt"));
    }
}