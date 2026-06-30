"""Generate a synthetic geometric pattern (cubes) for testing."""
import cv2
import numpy as np

def generate(output_path="evals/case-02/shop_drawing.png"):
    img = np.ones((800, 400, 3), dtype=np.uint8) * 255  # white background

    # Draw a series of isometric cubes
    for row in range(4):
        for col in range(2):
            x_offset = col * 200 + 20
            y_offset = row * 200 + 20
            
            # Top face
            pts_top = np.array([[x_offset+100, y_offset], 
                                [x_offset+200, y_offset+50], 
                                [x_offset+100, y_offset+100], 
                                [x_offset, y_offset+50]], np.int32)
            cv2.polylines(img, [pts_top], True, (0,0,0), 2)
            
            # Left face
            pts_left = np.array([[x_offset, y_offset+50], 
                                 [x_offset+100, y_offset+100], 
                                 [x_offset+100, y_offset+200], 
                                 [x_offset, y_offset+150]], np.int32)
            cv2.polylines(img, [pts_left], True, (0,0,0), 2)
            
            # Right face
            pts_right = np.array([[x_offset+100, y_offset+100], 
                                  [x_offset+200, y_offset+50], 
                                  [x_offset+200, y_offset+150], 
                                  [x_offset+100, y_offset+200]], np.int32)
            cv2.polylines(img, [pts_right], True, (0,0,0), 2)
            
            # Add some parallel lines on the faces
            for i in range(1, 4):
                # Top face lines
                cv2.line(img, (x_offset+i*25, y_offset+i*12), 
                         (x_offset+100+i*25, y_offset+50+i*12), (0,0,0), 1)
                # Left face lines
                cv2.line(img, (x_offset+i*25, y_offset+50+i*37), 
                         (x_offset+i*25, y_offset+150+i*12), (0,0,0), 1)

    cv2.imwrite(output_path, img)
    print(f"Generated shop test image: {output_path}")

if __name__ == "__main__":
    generate()
