from datetime import datetime, timezone


h3_index1 = "860123507ffffff"
h3_index2 = "860123cdfffffff"
h3_index3 = "860123537ffffff"
h3_index_lvl8 = "882990c2d1fffff"

time1 = datetime.strptime('2025-01-01', '%Y-%m-%d').replace(tzinfo=timezone.utc)
time2 = datetime.strptime('2025-01-02', '%Y-%m-%d').replace(tzinfo=timezone.utc)
time3 = datetime.strptime('2025-01-03', '%Y-%m-%d').replace(tzinfo=timezone.utc)
