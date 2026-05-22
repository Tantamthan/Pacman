import sys
from pacman.main import main

if __name__ == "__main__":
    print("=" * 30)
    print("  PACMAN GAME INTERFACE  ")
    print("=" * 30)
    print("1. Chạy với chế độ AI (AI Mode)")
    print("2. Chạy chế độ thông thường (Main Mode)")
    print("=" * 30)
    
    # Vòng lặp để bắt buộc người dùng nhập đúng lựa chọn 1 hoặc 2
    while True:
        choice = input("Nhập lựa chọn của bạn (1 hoặc 2): ").strip()
        
        if choice == '1':
            print("\nĐang khởi động chế độ AI...")
            # Giả lập việc truyền tham số '--ai' vào hệ thống
            sys.argv.append('--ai')
            main()
            break
        elif choice == '2':
            print("\nĐang khởi động chế độ thông thường...")
            # Chạy trực tiếp hàm main không có tham số
            main()
            break
        else:
            print("Lựa chọn không hợp lệ! Vui lòng chỉ nhấn 1 hoặc 2.")