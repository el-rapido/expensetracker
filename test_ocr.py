import os
from services.ocr_service import OCRService

def test_ocr():
    # Test with a sample image
    ocr = OCRService()
    
    # You can test with any image file
    test_image_path = "test_receipt.jpg"  # Put a test image here
    
    if os.path.exists(test_image_path):
        with open(test_image_path, 'rb') as f:
            image_data = f.read()
        
        result = ocr.extract_text_from_image(image_data)
        
        print("OCR Test Result:")
        print(f"Success: {result['success']}")
        print(f"Confidence: {result.get('confidence', 0):.2f}")
        print(f"Text: {result['text'][:200]}...")  # First 200 chars
    else:
        print("Please add a test_receipt.jpg file to test OCR")

if __name__ == "__main__":
    test_ocr()