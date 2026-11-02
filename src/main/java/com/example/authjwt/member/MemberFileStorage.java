package com.example.authjwt.member;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
 public class MemberFileStorage {
    private final Path root;

    public MemberFileStorage(@Value("${app.upload-dir:uploads}") String uploadDirectory) {
        this.root = Path.of(uploadDirectory).toAbsolutePath().normalize();
    }

    public String store(String memberReference, String category, String originalFilename, byte[] content) throws IOException {
        String reference = safePart(memberReference);
        if (reference.isBlank()) reference = "member";
        String extension = extension(originalFilename);
        Path target = root.resolve(reference)
                .resolve(safePart(category) + "-" + UUID.randomUUID() + extension)
                .normalize();
        if (!target.startsWith(root)) throw new IOException("Référence de fichier invalide");
        Files.createDirectories(target.getParent());
        Files.write(target, content);
        return root.relativize(target).toString().replace('\\', '/');
    }

    public byte[] read(String storageKey) throws IOException {
        return Files.readAllBytes(resolve(storageKey));
    }

    public void delete(String storageKey) throws IOException {
        if (storageKey != null && !storageKey.isBlank()) Files.deleteIfExists(resolve(storageKey));
    }

    private Path resolve(String storageKey) throws IOException {
        if (storageKey == null || storageKey.isBlank()) throw new IOException("Référence de fichier absente");
        Path path = root.resolve(storageKey).normalize();
        if (!path.startsWith(root)) throw new IOException("Référence de fichier invalide");
        return path;
    }

    private String safePart(String value) {
        return value == null ? "" : value.replaceAll("[^A-Za-z0-9_-]", "_");
    }

    private String extension(String filename) {
        if (filename == null) return "";
        String normalized = filename.replace('\\', '/');
        int dot = normalized.lastIndexOf('.');
        if (dot < 0) return "";
        String extension = normalized.substring(dot);
        return extension.matches("\\.[A-Za-z0-9]{1,10}") ? extension.toLowerCase(Locale.ROOT) : "";
    }
}