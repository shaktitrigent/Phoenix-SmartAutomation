import json

with open('D:/Phoniex/Phoenix-SmartAutomation/phoenix_runtime/dom/default/test_login_with_valid_credentials/latest_dom.json', 'r') as f:
    data = json.load(f)

dom = data['dom_content']
metadata = data['metadata']

print('=== DASHBOARD DOM VERIFICATION ===')
print(f'URL: {metadata["url"]}')
print(f'Elements: {metadata["num_elements"]}')
print(f'Size: {metadata["dom_size_bytes"]} bytes')
print(f'Timestamp: {metadata["timestamp"]}')
print()

print('Dashboard elements found:')
print(f'- oxd-main-menu: {"FOUND" if "oxd-main-menu" in dom else "NOT FOUND"}')
print(f'- dashboard: {"FOUND" if "dashboard" in dom.lower() else "NOT FOUND"}')
print(f'- Employee Distribution: {"FOUND" if "Employee Distribution" in dom else "NOT FOUND"}')
print(f'- Employees on Leave: {"FOUND" if "Employees on Leave" in dom else "NOT FOUND"}')
print(f'- John Doe: {"FOUND" if "John Doe" in dom else "NOT FOUND"}')
print(f'- orangehrm-dashboard-widget: {"FOUND" if "orangehrm-dashboard-widget" in dom else "NOT FOUND"}')
print(f'- Engineering: {"FOUND" if "Engineering" in dom else "NOT FOUND"}')
print(f'- Human Resources: {"FOUND" if "Human Resources" in dom else "NOT FOUND"}')
print(f'- Texas R&D: {"FOUND" if "Texas R&D" in dom else "NOT FOUND"}')
print(f'- New York Sales Office: {"FOUND" if "New York Sales Office" in dom else "NOT FOUND"}')
