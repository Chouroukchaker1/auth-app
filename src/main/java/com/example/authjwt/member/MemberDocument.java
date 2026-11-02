package com.example.authjwt.member;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;

import java.time.LocalDateTime;

@Entity
@Table(name = "member_documents")
public class MemberDocument {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "member_id")
    private Member member;

    private String typeFichier;
    private String filename;
    private String contentType;
    private long size;

    @Column(name = "content", columnDefinition = "bytea")
    private byte[] legacyContent;
    @Column(name = "storage_key")
    private String storageKey;

    /** When the file was uploaded; null for documents stored before this column existed. */
    private LocalDateTime createdAt;

    protected MemberDocument() {
    }

    @PrePersist
    void onCreate() {
        if (createdAt == null) {
            createdAt = LocalDateTime.now();
        }
    }

    public MemberDocument(Member member, String typeFichier, String filename, String contentType, long size, String storageKey) {
        this.member = member;
        this.typeFichier = typeFichier;
        this.filename = filename;
        this.contentType = contentType;
        this.size = size;
        this.storageKey = storageKey;
    }

    public Long getId() { return id; }
    public Member getMember() { return member; }
    public String getTypeFichier() { return typeFichier; }
    public String getFilename() { return filename; }
    public String getContentType() { return contentType; }
    public long getSize() { return size; }
    public byte[] getLegacyContent() { return legacyContent; }
    public void setLegacyContent(byte[] content) { this.legacyContent = content; }
    public String getStorageKey() { return storageKey; }
    public void setStorageKey(String storageKey) { this.storageKey = storageKey; }
    public LocalDateTime getCreatedAt() { return createdAt; }
}
