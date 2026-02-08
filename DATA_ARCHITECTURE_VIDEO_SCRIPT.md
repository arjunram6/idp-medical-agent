# Data Architecture – 2-Minute Video Script (Non-Technical)

**Audience:** Non-technical (e.g. program managers, partners, donors)  
**Length:** ~2 minutes  
**Tone:** Clear, simple, one idea per sentence.

---

## [0:00–0:20] **What is the data?**

"The tool is built around **one main source of truth**: a list of health facilities in Ghana—hospitals, clinics, pharmacies—with details like their name, location, what services they offer, contact information, and so on. Think of it like a **big, structured spreadsheet** that your team or Virtue Foundation maintains.

"There’s also a **short guide** that explains what each column means—for example, what we mean by 'capability' or 'specialty.' That way the tool and the people using it are all using the same definitions."

---

## [0:20–0:50] **Where does it live and who can use it?**

"The data lives **on your computer**—in a folder called *data*, or on your Desktop. The tool looks there first. You don’t need the internet to *store* or *read* this data; it’s yours.

"When you ask a question, the tool **reads that spreadsheet** and, depending on the question, either answers directly from it or uses it plus a search step and optional AI to give you a clear, written answer. So: **one place for the data, one place the tool looks**—no hidden copies or scattered files for the main Ghana list."

---

## [0:50–1:25] **How does the tool use the data?**

"The tool uses the data in **two main ways**.

"**First, quick lookups.** Questions like 'How many hospitals in Accra?' or 'What services does Methodist Clinic offer?' are answered **directly from the spreadsheet**. The tool finds the right rows, counts or reads the fields, and gives you the answer. Fast, and you can trace it back to the sheet.

"**Second, deeper search.** For questions like 'Where can I get cardiac care?' or 'Which facilities have the most complete information?', the tool **indexes** the facility descriptions—that just means it makes them searchable by meaning, not only by exact words—and then can combine that with **risk scores** and **filters** (e.g. by region or facility type). So you get answers that are still grounded in your data, with the tool pointing to **which facilities and which fields** it used. That’s how we keep it transparent and auditable."

---

## [1:25–1:55] **What about risk, location, and other data?**

"The tool can **score each facility** on how complete its information is—things like: Do we have contact info? Do we know the facility type? Do we have location and services? Those scores help you see which places are **well documented** and which need better data. That’s the **risk and data-quality** side.

"**Location** can be improved by adding latitude and longitude to the spreadsheet (geocoding). Then the tool can answer questions like 'facilities within 5 km of Accra' using **distance on a map**, not just the name of the city.

"**Other data**—for example, data that isn’t in the main Ghana list yet—can be added as **external sources**. The tool is designed so that the main facility list stays the core, and extra sources can be plugged in when needed."

---

## [1:55–2:00] **Wrap-up**

"So in short: **one main dataset** (your Ghana facility list and its guide), **one place it lives** (your data folder or Desktop), and **one tool** that reads it in different ways—direct lookups, search, risk scoring, and optional location and external data—so you get answers you can trust and trace back to the data."

---

## Optional one-liner for the very end

"The data architecture is: **your list, your machine, one source of truth—the tool just reads it the right way for each question.**"
