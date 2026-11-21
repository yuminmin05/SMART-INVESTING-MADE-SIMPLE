# Smart DCA Portfolio Optimizer (Genetic Algorithm)

เว็บแอปพลิเคชัน Django สำหรับทดลองจัดสัดส่วนพอร์ตหุ้น SET50 ด้วย Genetic Algorithm (GA) โดยใช้มูลค่าเงินลงทุนในอนาคตจากการลงทุน DCA รายเดือนเป็น Fitness Function และเปรียบเทียบระยะเวลา 1, 5 และ 10 ปี

## แนวคิดการทำงานของ GA

- **Chromosome:** เวกเตอร์น้ำหนักของหุ้นที่ผู้ใช้เลือก โดยแต่ละยีนแทนสัดส่วนลงทุนของหุ้นหนึ่งตัว
- **Constraint:** น้ำหนักทุกยีนไม่ติดลบ และผลรวมเท่ากับ 1 (หรือ 100%)
- **Portfolio return:** คำนวณจากผลตอบแทนรายปีแบบถ่วงน้ำหนัก `Rp = sum(w_i * R_i)`
- **Monthly return:** แปลง effective annual return เป็นอัตรารายเดือน `r = (1 + Rp)^(1/12) - 1`
- **Fitness:** คำนวณ Future Value แบบ Annuity Due (ลงทุนต้นเดือน)

สูตร Fitness:

`FV = PMT * [((1 + r)^n - 1) / r] * (1 + r)`

เมื่อ `r = 0` ใช้ `FV = PMT * n` และเมื่อผลตอบแทนรายปีเท่ากับ -100% กำหนด FV เป็น 0

## Genetic Algorithm Operators

- **Selection:** Tournament Selection
- **Crossover:** Simulated Binary Crossover (SBX)
- **Mutation:** Gaussian Mutation และ normalize น้ำหนักกลับให้อยู่ใน simplex
- **Elitism:** เก็บสมาชิกที่มี Fitness สูงสุดไว้ในประชากรรุ่นถัดไป
- **Objective:** Maximize Future Value

## ค่า GA เริ่มต้นในหน้าเว็บ

| Parameter | ค่า |
|---|---:|
| Population Size | 60 |
| Generations | 100 |
| Crossover Probability | 0.90 |
| Mutation Rate | 0.10 |
| Mutation Sigma | 0.05 |
| SBX Eta (eta_c) | 20 |
| Tournament Size | 3 |
| Elite Size | 2 |

API สามารถรับ `ga_params` เพื่อปรับค่าพารามิเตอร์ได้ และรองรับ `seed` สำหรับการทดลองซ้ำแบบกำหนดค่าเริ่มต้นเดียวกัน

## โครงสร้างโปรเจกต์

```text
manage.py
requirements.txt
README.md
smart_dca/
portfolio/
  migrations/
  models.py
  optimizer.py       # สูตร Annuity Due และ Genetic Algorithm
  stocks.py          # หุ้น SET50 และค่าเริ่มต้นผลตอบแทน
  urls.py
  views.py           # API และ background worker
  tests.py
templates/portfolio/index.html
static/portfolio/app.js
static/portfolio/styles.css
```

## วิธีติดตั้งและรัน (Windows PowerShell)

1. ติดตั้ง Python 3.11 ขึ้นไป และเปิด PowerShell ในโฟลเดอร์โปรเจกต์
2. สร้าง virtual environment และเปิดใช้งาน:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. ติดตั้ง dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. สร้างฐานข้อมูล SQLite:

   ```powershell
   python manage.py migrate
   ```

5. เริ่มเว็บเซิร์ฟเวอร์:

   ```powershell
   python manage.py runserver
   ```

6. เปิด `http://127.0.0.1:8000/`

## API

- `GET /api/stocks/` คืนหุ้น SET50 และผลตอบแทนต่อปี
- `POST /api/stocks/` บันทึกค่า return เช่น `{"returns":{"AOT":3.2,"BCH":4.1}}`
- `POST /api/optimize/` รับ `{"stocks":["AOT","ADVANC"],"monthly_money":10000,"ga_params":{"population_size":60,"generations":100}}` และคืน `202` พร้อม `job_id`
- `GET /api/optimize/<job_id>/` ใช้ polling ดูสถานะและผลลัพธ์ รวมถึง Fitness History

งานคำนวณทำงานใน background thread และสถานะเก็บในหน่วยความจำ เหมาะกับการพัฒนา/รันเซิร์ฟเวอร์ worker เดียว หากใช้งาน production หรือหลาย process ควรเปลี่ยน job store เป็น Celery/Redis หรือ task queue ที่แชร์สถานะได้

## การทดสอบ

```powershell
python manage.py test portfolio
```

## สมมติฐานและข้อจำกัด

- ผลตอบแทนหุ้นเป็น effective annual return คงที่ตลอดช่วงจำลอง
- เงินลงทุนรายเดือนถูกสมมติว่าลงทุนต้นเดือน (Annuity Due) ตามสูตรในภาพประกอบ
- ผลตอบแทน 5 หุ้นแรกย้ายตามค่า `S_Dict` ที่มีในชุดข้อมูลเดิม หุ้นที่เหลือเริ่มต้นด้วย placeholder `1.0%` ต่อปี ผู้ใช้สามารถแก้และบันทึกใน SQLite ได้
- ช่อง “อัปเดตจาก Yahoo Finance” เป็นจุดต่อยอด UI เท่านั้น ยังไม่มีการเรียก Yahoo Finance หรือแปลงข้อมูลราคาเป็นผลตอบแทนจริง
- Fitness ปัจจุบันพิจารณา Future Value เท่านั้น ยังไม่มีการลงโทษความเสี่ยง ความผันผวน หรือการกระจุกตัวของพอร์ต
- เนื่องจาก Fitness เป็นฟังก์ชันเพิ่มตามผลตอบแทนพอร์ตและไม่มีข้อจำกัดความเสี่ยง คำตอบที่เหมาะที่สุดอาจโน้มไปยังหุ้นที่มีผลตอบแทนสมมติฐานสูงสุด แม้ใช้ GA ค้นหาอยู่ก็ตาม
- GA เป็นวิธีค้นหาเชิงสุ่ม จึงอาจได้ผลต่างกันในแต่ละครั้ง หากต้องการทำซ้ำให้ส่ง `seed` ค่าเดิม
- ค่าผลตอบแทนเป็นสมมติฐานเพื่อสาธิต ไม่ใช่ข้อมูลราคา/ผลตอบแทนที่รับประกัน และไม่ใช่คำแนะนำการลงทุน
- Tailwind CSS, Chart.js และฟอนต์โหลดจาก CDN จึงต้องเชื่อมต่ออินเทอร์เน็ตเพื่อใช้งานส่วนดังกล่าว
- ปุ่ม PDF ใช้หน้าต่างพิมพ์ของเบราว์เซอร์ (เลือก Save as PDF) ส่วน CSV ดาวน์โหลดผลที่คำนวณ
