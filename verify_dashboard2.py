import json

with open('D:/Phoniex/Phoenix-SmartAutomation/phoenix_runtime/dom/default/test_login_with_valid_credentials/latest_dom.json', 'r') as f:
    data = json.load(f)

dom = data['dom_content']

print('=== DASHBOARD DOM CONTENT SAMPLE ===')
print('Looking for employee-related content...')

# Search for employee-related patterns
if 'employee' in dom.lower():
    print('Found "employee" in DOM')
    # Extract a snippet around the first occurrence
    idx = dom.lower().find('employee')
    print(f'Sample around employee: {dom[max(0, idx-50):min(len(dom), idx+200)]}')
else:
    print('No "employee" found in DOM')

if 'leave' in dom.lower():
    print('Found "leave" in DOM')
    idx = dom.lower().find('leave')
    print(f'Sample around leave: {dom[max(0, idx-50):min(len(dom), idx+200)]}')

if 'CAN' in dom:
    print('Found "CAN" in DOM')
    idx = dom.find('CAN')
    print(f'Sample around CAN: {dom[max(0, idx-50):min(len(dom), idx+200)]}')
