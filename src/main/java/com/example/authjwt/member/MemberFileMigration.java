package com.example.authjwt.member;

import java.io.IOException;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class MemberFileMigration implements ApplicationRunner {
    private final MemberRepository memberRepository;
    private final MemberFileStorage fileStorage;

    public MemberFileMigration(MemberRepository memberRepository, MemberFileStorage fileStorage) {
        this.memberRepository = memberRepository;
        this.fileStorage = fileStorage;
    }

    @Override
    @Transactional
    public void run(ApplicationArguments args) throws IOException {
        for (Member member : memberRepository.findAll()) {
            migrateMemberFile(member.getNumeroUnifie(), "photo", member.getLegacyPhoto(), member.getPhotoStorageKey(),
                    member::setPhotoStorageKey, member::setLegacyPhoto);
            migrateMemberFile(member.getNumeroUnifie(), "carte-soins", member.getLegacyCarteSoins(), member.getCarteSoinsStorageKey(),
                    member::setCarteSoinsStorageKey, member::setLegacyCarteSoins);
            migrateMemberFile(member.getNumeroUnifie(), "carte-militaire", member.getLegacyCarteMilitaire(), member.getCarteMilitaireStorageKey(),
                    member::setCarteMilitaireStorageKey, member::setLegacyCarteMilitaire);
            for (MemberDocument document : member.getDocuments()) {
                if (document.getStorageKey() == null && document.getLegacyContent() != null) {
                    document.setStorageKey(fileStorage.store(member.getNumeroUnifie(), "document", document.getFilename(), document.getLegacyContent()));
                    document.setLegacyContent(null);
                }
            }
        }
    }

    private void migrateMemberFile(String reference, String category, byte[] content, String currentKey,
                                   java.util.function.Consumer<String> setKey,
                                   java.util.function.Consumer<byte[]> clearLegacy) throws IOException {
        if (currentKey == null && content != null) {
            setKey.accept(fileStorage.store(reference, category, null, content));
            clearLegacy.accept(null);
        }
    }
}