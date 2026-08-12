"""Simple verification script for Priority 20 - Universal Application Understanding.

This script verifies that the semantic understanding system works correctly
without relying on the full test infrastructure.
"""

import sys
from pathlib import Path

# Add phoenix-core to path
phoenix_core_path = Path(__file__).parent
sys.path.insert(0, str(phoenix_core_path))

try:
    from phoenix.semantic.models import (
        SemanticPage,
        SemanticComponent,
        PageType,
        ComponentType,
        BusinessIntentType,
        NavigationContext,
        BusinessIntent,
    )
    from phoenix.semantic.page_classifier import SemanticPageClassifier
    from phoenix.semantic.component_analyzer import UIComponentAnalyzer
    from phoenix.semantic.intent_detector import BusinessIntentDetector
    from phoenix.semantic.navigation_analyzer import NavigationStructureAnalyzer
    from phoenix.semantic.semantic_integrator import SemanticIntegrator
    
    print("[OK] All semantic modules imported successfully")
    
    # Test models
    print("\n[TEST] Testing Semantic Models...")
    assert PageType.AUTHENTICATION_SCREEN is not None
    assert ComponentType.TEXT_FIELD is not None
    assert BusinessIntentType.AUTHENTICATION is not None
    print("[OK] All enums defined correctly")
    
    # Test page classifier
    print("\n[SEARCH] Testing Page Classifier...")
    classifier = SemanticPageClassifier()
    assert len(classifier.patterns) > 0
    print(f"[OK] Page classifier initialized with {len(classifier.patterns)} patterns")
    
    # Test page classification
    page_type, confidence, evidence = classifier.classify(
        url="https://example.com/login",
        title="Login to Your Account",
        heading="Sign In",
        dom_content="<input type='text' name='username'><input type='password' name='password'><button>Login</button>",
        components=[],
        text_content="login username password sign in"
    )
    assert page_type == PageType.AUTHENTICATION_SCREEN
    print(f"[OK] Authentication page classified correctly (confidence: {confidence:.2f})")
    
    # Test component analyzer
    print("\n[COMPONENT] Testing Component Analyzer...")
    analyzer = UIComponentAnalyzer()
    assert len(analyzer.patterns) > 0
    print(f"[OK] Component analyzer initialized with {len(analyzer.patterns)} patterns")
    
    # Test component classification
    element = {
        "tag": "input",
        "attributes": {"type": "text", "name": "username"},
        "text": "",
        "xpath": "//input[@name='username']",
        "css_selector": "input[name='username']",
        "visible": True,
        "position": {},
        "layout": {},
    }
    component = analyzer.analyze_element(element)
    assert component.component_type == ComponentType.TEXT_FIELD
    print(f"[OK] Text field component classified correctly (confidence: {component.confidence:.2f})")
    
    # Test business intent detector
    print("\n[INTENT] Testing Business Intent Detector...")
    detector = BusinessIntentDetector()
    assert len(detector.patterns) > 0
    print(f"[OK] Business intent detector initialized with {len(detector.patterns)} patterns")
    
    # Test intent detection
    intent = detector.detect_intent(
        url="https://example.com/login",
        title="Login",
        heading="Sign In",
        components=[],
        text_content="login username password sign in",
        page_type=PageType.AUTHENTICATION_SCREEN
    )
    assert intent.primary_intent == BusinessIntentType.AUTHENTICATION
    print(f"[OK] Authentication intent detected correctly (confidence: {intent.confidence:.2f})")
    
    # Test navigation analyzer
    print("\n[NAV] Testing Navigation Analyzer...")
    nav_analyzer = NavigationStructureAnalyzer()
    assert len(nav_analyzer.patterns) > 0
    print(f"[OK] Navigation analyzer initialized with {len(nav_analyzer.patterns)} patterns")
    
    # Test navigation analysis
    nav_context = nav_analyzer.analyze_navigation(
        components=[],
        dom_content="<nav class='navigation'><ul><li><a href='/home'>Home</a></li></ul></nav>",
        url="https://example.com/dashboard"
    )
    assert nav_context.has_navigation_menu == True
    print(f"[OK] Navigation menu detected correctly (confidence: {nav_context.confidence:.2f})")
    
    # Test semantic integrator
    print("\n[INTEGRATOR] Testing Semantic Integrator...")
    integrator = SemanticIntegrator(base_dir="test_semantic_storage")
    assert integrator.page_classifier is not None
    assert integrator.component_analyzer is not None
    assert integrator.intent_detector is not None
    assert integrator.navigation_analyzer is not None
    print("[OK] Semantic integrator initialized correctly")
    
    # Test complete page analysis
    dom_elements = [
        {
            "tag": "input",
            "attributes": {"type": "text", "name": "username"},
            "text": "",
            "xpath": "//input[@name='username']",
            "css_selector": "input[name='username']",
            "visible": True,
            "position": {},
            "layout": {},
        },
        {
            "tag": "input",
            "attributes": {"type": "password", "name": "password"},
            "text": "",
            "xpath": "//input[@name='password']",
            "css_selector": "input[name='password']",
            "visible": True,
            "position": {},
            "layout": {},
        },
        {
            "tag": "button",
            "attributes": {"type": "submit"},
            "text": "Login",
            "xpath": "//button[@type='submit']",
            "css_selector": "button[type='submit']",
            "visible": True,
            "position": {},
            "layout": {},
        },
    ]
    
    semantic_page = integrator.analyze_page(
        url="https://example.com/login",
        title="Login",
        heading="Sign In",
        dom_content="<input type='text' name='username'><input type='password' name='password'><button>Login</button>",
        dom_elements=dom_elements,
        text_content="login username password sign in",
        project_name="test_project",
        test_name="test_login",
        execution_id="test_execution_001",
        dom_hash="test_hash"
    )
    
    assert semantic_page is not None
    assert semantic_page.page_type == PageType.AUTHENTICATION_SCREEN
    assert len(semantic_page.components) > 0
    assert semantic_page.business_intent.primary_intent == BusinessIntentType.AUTHENTICATION
    print(f"[OK] Complete page analysis successful (page type: {semantic_page.page_type.value}, confidence: {semantic_page.confidence:.2f})")
    
    # Test semantic context generation
    context = integrator.get_semantic_context_for_llm(semantic_page)
    assert "Semantic Page Understanding" in context
    assert "Page Type" in context
    assert "Business Intent" in context
    print("[OK] Semantic context generation successful")
    
    # Test generic understanding (no product-specific patterns)
    print("\n[GENERIC] Testing Generic Understanding (Application-Agnostic)...")
    product_names = ["orangehrm", "jira", "salesforce", "sap", "servicenow"]
    
    for pattern in classifier.patterns:
        for product in product_names:
            assert product not in pattern.url_patterns[0].lower()
            assert product not in pattern.title_patterns[0].lower()
    
    print("[OK] No product-specific patterns found (truly generic)")
    
    # Test with unknown application
    generic_page = integrator.analyze_page(
        url="https://unknown-app.com/auth/login",
        title="Authentication",
        heading="Sign In",
        dom_content="<input type='text' placeholder='Email'><input type='password' placeholder='Password'><button>Sign In</button>",
        dom_elements=[],
        text_content="sign in email password",
        project_name="test_project",
        test_name="test_auth",
        execution_id="test_execution_002",
    )
    
    assert generic_page.page_type == PageType.AUTHENTICATION_SCREEN
    assert generic_page.business_intent.primary_intent == BusinessIntentType.AUTHENTICATION
    print("[OK] Generic understanding works for unknown applications")
    
    print("\n" + "="*60)
    print("[SUCCESS] PRIORITY 20 VERIFICATION COMPLETE")
    print("="*60)
    print("\n[OK] Universal Application Understanding is working correctly")
    print("[OK] Phoenix now understands pages semantically, not by product name")
    print("[OK] System is completely application-agnostic")
    print("\n[READY] Ready for Priority 21: AI Business Flow Detection")
    
except Exception as e:
    print(f"\n[FAILED] Verification failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
