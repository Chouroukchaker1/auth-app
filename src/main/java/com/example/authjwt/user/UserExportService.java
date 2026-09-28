package com.example.authjwt.user;

import com.lowagie.text.Document;
import com.lowagie.text.Font;
import com.lowagie.text.PageSize;
import com.lowagie.text.Paragraph;
import com.lowagie.text.Phrase;
import com.lowagie.text.pdf.PdfPCell;
import com.lowagie.text.pdf.PdfPTable;
import com.lowagie.text.pdf.PdfWriter;
import java.awt.Color;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.List;
import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.stereotype.Service;

@Service
public class UserExportService {
    private final UserRepository userRepository;

    public UserExportService(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    public byte[] exportPdf() {
        List<User> users = userRepository.findAll();
        try (ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            Document document = new Document(PageSize.A4);
            PdfWriter.getInstance(document, output);
            document.open();
            document.add(new Paragraph("Liste des utilisateurs", new Font(Font.HELVETICA, 18, Font.BOLD)));

            PdfPTable table = new PdfPTable(new float[] { 2.2f, 3.2f, 1.3f });
            table.setWidthPercentage(100);
            table.setSpacingBefore(18);
            addHeaderCell(table, "Nom complet");
            addHeaderCell(table, "Email");
            addHeaderCell(table, "Rôle");
            for (User user : users) {
                table.addCell(user.getFullName());
                table.addCell(user.getEmail());
                table.addCell(user.getRole());
            }
            document.add(table);
            document.close();
            return output.toByteArray();
        } catch (IOException exception) {
            throw new IllegalStateException("Impossible de générer le PDF", exception);
        }
    }

    public byte[] exportExcel() {
        List<User> users = userRepository.findAll();
        try (Workbook workbook = new XSSFWorkbook(); ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            Sheet sheet = workbook.createSheet("Utilisateurs");
            Row header = sheet.createRow(0);
            addCell(header, 0, "Nom complet");
            addCell(header, 1, "Email");
            addCell(header, 2, "Rôle");
            for (int index = 0; index < users.size(); index++) {
                User user = users.get(index);
                Row row = sheet.createRow(index + 1);
                addCell(row, 0, user.getFullName());
                addCell(row, 1, user.getEmail());
                addCell(row, 2, user.getRole());
            }
            sheet.autoSizeColumn(0);
            sheet.autoSizeColumn(1);
            sheet.autoSizeColumn(2);
            workbook.write(output);
            return output.toByteArray();
        } catch (IOException exception) {
            throw new IllegalStateException("Impossible de générer le fichier Excel", exception);
        }
    }

    private void addHeaderCell(PdfPTable table, String value) {
        PdfPCell cell = new PdfPCell(new Phrase(value, new Font(Font.HELVETICA, 10, Font.BOLD)));
        cell.setBackgroundColor(new Color(37, 99, 235));
        cell.setPhrase(new Phrase(value, new Font(Font.HELVETICA, 10, Font.BOLD, Color.WHITE)));
        cell.setHorizontalAlignment(PdfPCell.ALIGN_LEFT);
        cell.setPadding(7);
        table.addCell(cell);
    }

    private void addCell(Row row, int column, String value) {
        Cell cell = row.createCell(column);
        cell.setCellValue(value);
    }
}