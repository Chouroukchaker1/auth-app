package com.example.authjwt.member;

import com.example.authjwt.user.User;
import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.OneToMany;
import jakarta.persistence.OneToOne;
import jakarta.persistence.OrderColumn;
import jakarta.persistence.Table;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "members")
public class Member {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @OneToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", unique = true)
    private User user;

    private String numeroUnifie;
    private String cnr;
    private String numeroAffiliation;
    private String typeService;

    private String nomPrenom;
    private String grade;
    private LocalDate dateNaissance;
    private String lieuNaissance;
    private LocalDate debutActivite;
    private String statut;

    private String etatCivil;
    private LocalDate dateMariage;

    @Column(columnDefinition = "bytea")
    private byte[] photo;
    private String photoContentType;

    @Column(columnDefinition = "bytea")
    private byte[] carteSoins;
    private String carteSoinsContentType;

    @Column(columnDefinition = "bytea")
    private byte[] carteMilitaire;
    private String carteMilitaireContentType;

    @OneToMany(mappedBy = "member", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderColumn(name = "position")
    private List<FamilyMember> familyMembers = new ArrayList<>();

    @OneToMany(mappedBy = "member", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<MemberDocument> documents = new ArrayList<>();

    public Long getId() { return id; }
    public User getUser() { return user; }
    public void setUser(User user) { this.user = user; }

    public String getNumeroUnifie() { return numeroUnifie; }
    public void setNumeroUnifie(String numeroUnifie) { this.numeroUnifie = numeroUnifie; }
    public String getCnr() { return cnr; }
    public void setCnr(String cnr) { this.cnr = cnr; }
    public String getNumeroAffiliation() { return numeroAffiliation; }
    public void setNumeroAffiliation(String numeroAffiliation) { this.numeroAffiliation = numeroAffiliation; }
    public String getTypeService() { return typeService; }
    public void setTypeService(String typeService) { this.typeService = typeService; }
    public String getNomPrenom() { return nomPrenom; }
    public void setNomPrenom(String nomPrenom) { this.nomPrenom = nomPrenom; }
    public String getGrade() { return grade; }
    public void setGrade(String grade) { this.grade = grade; }
    public LocalDate getDateNaissance() { return dateNaissance; }
    public void setDateNaissance(LocalDate dateNaissance) { this.dateNaissance = dateNaissance; }
    public String getLieuNaissance() { return lieuNaissance; }
    public void setLieuNaissance(String lieuNaissance) { this.lieuNaissance = lieuNaissance; }
    public LocalDate getDebutActivite() { return debutActivite; }
    public void setDebutActivite(LocalDate debutActivite) { this.debutActivite = debutActivite; }
    public String getStatut() { return statut; }
    public void setStatut(String statut) { this.statut = statut; }
    public String getEtatCivil() { return etatCivil; }
    public void setEtatCivil(String etatCivil) { this.etatCivil = etatCivil; }
    public LocalDate getDateMariage() { return dateMariage; }
    public void setDateMariage(LocalDate dateMariage) { this.dateMariage = dateMariage; }

    public byte[] getPhoto() { return photo; }
    public void setPhoto(byte[] photo) { this.photo = photo; }
    public String getPhotoContentType() { return photoContentType; }
    public void setPhotoContentType(String photoContentType) { this.photoContentType = photoContentType; }
    public byte[] getCarteSoins() { return carteSoins; }
    public void setCarteSoins(byte[] carteSoins) { this.carteSoins = carteSoins; }
    public String getCarteSoinsContentType() { return carteSoinsContentType; }
    public void setCarteSoinsContentType(String carteSoinsContentType) { this.carteSoinsContentType = carteSoinsContentType; }
    public byte[] getCarteMilitaire() { return carteMilitaire; }
    public void setCarteMilitaire(byte[] carteMilitaire) { this.carteMilitaire = carteMilitaire; }
    public String getCarteMilitaireContentType() { return carteMilitaireContentType; }
    public void setCarteMilitaireContentType(String carteMilitaireContentType) { this.carteMilitaireContentType = carteMilitaireContentType; }

    public List<FamilyMember> getFamilyMembers() { return familyMembers; }
    public List<MemberDocument> getDocuments() { return documents; }
}
