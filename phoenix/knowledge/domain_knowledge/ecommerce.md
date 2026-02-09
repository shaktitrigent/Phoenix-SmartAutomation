---
title: E-commerce Domain Knowledge
category: domain
tags: [ecommerce, shopping, cart, checkout, payment]
---

# E-commerce Domain Knowledge

## Description
Domain-specific knowledge for e-commerce applications, including common workflows and business rules.

## Common Workflows

### Shopping Flow
1. Browse products
2. Add to cart
3. View cart
4. Proceed to checkout
5. Enter shipping information
6. Select payment method
7. Review order
8. Place order
9. Receive confirmation

### User Account Flow
1. Register/Login
2. View profile
3. Manage addresses
4. View order history
5. Track orders
6. Manage wishlist

## Business Rules

### Cart Management
- Cart persists across sessions (logged-in users)
- Cart expires after inactivity period
- Maximum quantity per item
- Minimum order value for checkout
- Shipping costs calculated based on location

### Payment Processing
- Multiple payment methods supported
- Payment validation before order confirmation
- Refund processing rules
- Payment gateway integration

### Inventory Management
- Stock availability checks
- Out-of-stock handling
- Pre-order functionality
- Backorder management

## Test Scenarios

### Critical Paths
1. **Product Purchase:** Complete purchase flow end-to-end
2. **Cart Operations:** Add, update, remove items
3. **Checkout Process:** Complete checkout with valid data
4. **Payment Processing:** Successful payment transaction
5. **Order Management:** View and track orders

### Edge Cases
1. Out-of-stock items
2. Expired cart sessions
3. Payment failures
4. Invalid shipping addresses
5. Coupon code validation

## Common Validations

- Email format validation
- Phone number format
- Address validation
- Credit card number format
- CVV validation
- Expiry date validation
- Postal code validation

## Domain-Specific Test Patterns

- Product search and filtering
- Shopping cart persistence
- Checkout form validation
- Payment gateway integration
- Order confirmation emails
- Inventory synchronization
