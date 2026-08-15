"""Probe lock()/restore() for candidate defect classes (slice 2, Track 1)."""
import sys
sys.path.insert(0, "C:/Users/Admin/Humanize")
from untell.scripts.preserve import lock, restore

CASES = [
    # (label, text)
    ("A url trailing period", "See https://example.com. Then we left."),
    ("A2 url trailing ?", "See https://example.com/path?q=1. Then we left."),
    ("B doi trailing period", "See doi:10.1000/xyz. Then we left."),
    ("C win path trailing period", "Open C:\\data\\file.txt. Then we left."),
    ("C2 unix path trailing period", "Open src/main.py. Then we left."),
    ("D pm 5%", "The result is ±5%. It matters."),
    ("D2 pm temp", "Within ± 2.5 °C of the target. Next."),
    ("D3 pm plain", "The value was ±3. It changed."),
    ("E range percent", "5–10% of patients improved. The rest did not."),
    ("E2 range percent hyphen", "10-20% of the samples failed. Then what?"),
    ("F m/s", "The speed was 10 m/s. It was fast."),
    ("F2 kg/m3", "The density is 5 kg/m³. It is heavy."),
    ("F3 m2", "The area is 25 m². It is large."),
    ("F4 g/cm3", "Density was 2.3 g/cm³. It sank."),
    ("G exp 10^9", "The count was 1.5 × 10^9 cells. It grew."),
    ("G2 exp e", "The count was 1.5e9 cells. It grew."),
    ("H month day no year", "The deadline is March 15. Then we rest."),
    ("H2 month day end", "Christmas is December 25."),
    ("I p range", "See p. 4-5 for details. Then what?"),
    ("I2 pp range", "See pp. 10–20 for details."),
    ("J phone uk spaced", "Call +44 20 7946 0958. Then leave."),
    ("J2 phone uk 0", "Call 020 7946 0958 today. It is urgent."),
    ("J3 phone spaced us", "Call 123 456 7890 now. It is urgent."),
    ("J4 phone parens", "Call (555) 123-4567 now. It is urgent."),
    ("J5 phone e164 period", "Call +1-555-123-4567. Then leave."),
    ("J6 phone compact", "Call +44 2079460958. Then leave."),
    ("K thousands decimal", "Revenue was 1,234,567.89 last year. It rose."),
    ("L time range am", "Open 9:30–10:30 AM daily. Then close."),
    ("L2 time range bare", "From 9:30-10:30 we work. Then rest."),
    ("M 5 p.m.", "The meeting is at 5 p.m. Then we left."),
    ("M2 9 a.m.", "We start at 9 a.m. sharp. Then coffee."),
    ("O 3.5M", "The cap is 3.5M. It is high."),
    ("O2 5K", "The run is 5K. It is short."),
    ("N email co.uk", "Write to foo@bar.co.uk. Then send."),
    ("N2 email in brackets", "Email <foo@bar.com> today."),
    ("Q 50 %", "Add 50 % more. Then mix."),
    ("S 1.5E+10", "The mass is 1.5E+10 kg. It is huge."),
    ("T 12:30 p.m.", "Lunch is at 12:30 p.m. Then work."),
    ("U years range", "Covered 2010-2015 in depth. Then skip."),
    ("V 10-20%", "10-20% of patients recovered. Great."),
    ("W dotted abbr comma", "(e.g., small branches or blurred edges) then done."),
    ("X version v1.2.3", "Use v1.2.3 of the tool. Then test."),
    ("Y bare 1.2.3", "Requires numpy 1.26.4 or newer. Then run."),
    ("Z decimal 0.05", "The p-value was 0.05. It is borderline."),
    ("AA ratio words", "The odds were 1 in 5. Then changed."),
    ("BB quoted period", 'He said "Done." Then he left.'),
    ("CC e.g. lowercase", "Use tools (e.g. hammers) for this. Then stop."),
    ("DD 5 mg", "Give 5 mg twice daily. Then stop."),
    ("EE 16 GB", "The file is 16 GB in size. Then upload."),
    ("FF percentile", "She scored in the 95th percentile. Then left."),
    ("GG concentration", "The solution is 5 M HCl. It is strong."),
]

bad = 0
for label, text in CASES:
    masked, mapping = lock(text)
    restored = restore(masked, mapping)
    ok = restored == text
    if not ok:
        bad += 1
        print(f"ROUNDTRIP-BREAK {label}: {text!r} -> {restored!r}")
    else:
        # show lock behavior
        print(f"{label}: {masked!r}")
print(f"\nroundtrip failures: {bad}/{len(CASES)}")
