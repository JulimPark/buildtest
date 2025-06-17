import flet as ft
from flet import Paint, StrokeCap, StrokeJoin
from flet.canvas import Canvas, Path
import math
import time # 시간 측정을 위해 time 모듈 추가


# 각 드로잉 획을 관리하기 위한 클래스
class Stroke:
    def __init__(self, color, width):
        # 획을 구성하는 원본 (x, y) 좌표 목록
        self.points = []
        # Flet Canvas에 그려질 Path 객체
        self.path = Path([], Paint(
            stroke_width=width,
            color=color,
            style=ft.PaintingStyle.STROKE,
            stroke_cap=StrokeCap.ROUND,
            stroke_join=StrokeJoin.ROUND,
        ))
        # 현재 선택되었는지 여부
        self.is_selected = False
        # 획의 기본 색상과 두께 저장 (선택 시 하이라이트 등에 사용)
        self.color = color
        self.width = width # 이 width는 이제 '기본' 또는 '초기' 두께 역할을 할 수 있음
        # 획의 경계 상자(bounding box)를 위한 최소/최대 좌표
        self.min_x = float('inf')
        self.max_x = float('-inf')
        self.min_y = float('inf')
        self.max_y = float('-inf')

    # 획에 새로운 점 추가
    def add_point(self, x, y):
        self.points.append((x, y))
        if not self.path.elements:
            # 첫 점이면 PathMoveTo로 시작
            self.path.elements.append(Path.MoveTo(x, y))
        else:
            # 이후 점이면 PathLineTo로 선 연결
            self.path.elements.append(Path.LineTo(x, y))
        
        # 경계 상자 업데이트
        self.min_x = min(self.min_x, x)
        self.max_x = max(self.max_x, x)
        self.min_y = min(self.min_y, y)
        self.max_y = max(self.max_y, y)

    # 특정 (x, y) 좌표가 획에 "충돌"하는지 (즉, 선택되었는지) 확인
    # 간단한 경계 상자 충돌 테스트를 사용
    def is_hit(self, x, y, tolerance=5):
        if not self.points:
            return False
        
        # 획의 두께와 선택을 위한 허용 오차를 고려하여 경계 상자 확장
        # 현재 Path의 획 두께를 사용 (동적으로 변할 수 있기 때문)
        effective_tolerance = tolerance + self.path.paint.stroke_width / 2 

        return (self.min_x - effective_tolerance <= x <= self.max_x + effective_tolerance and
                self.min_y - effective_tolerance <= y <= self.max_y + effective_tolerance)

    # 획의 점 목록을 기반으로 Path 요소들을 다시 생성
    # 획이 이동하거나 크기가 변경될 때 호출됨
    def update_path_elements(self):
        if not self.points:
            self.path.elements = []
            return

        elements = []
        # 첫 점은 PathMoveTo
        elements.append(Path.MoveTo(self.points[0][0], self.points[0][1]))
        # 나머지 점들은 PathLineTo
        for i in range(1, len(self.points)):
            elements.append(Path.LineTo(self.points[i][0], self.points[i][1]))
        self.path.elements = elements

        # 선택 상태에 따라 획의 색상과 두께 변경 (하이라이트 효과)
        if self.is_selected:
            self.path.paint.color = ft.Colors.BLUE_200 # 선택 시 강조 색상
            self.path.paint.stroke_width = self.width + 2 # 선택 시 약간 두껍게 (기본 width를 기준으로)
        else:
            self.path.paint.color = self.color # 기본 색상
            self.path.paint.stroke_width = self.width # 기본 두께

    # 획을 이동시키는 함수
    def translate(self, dx, dy):
        for i in range(len(self.points)):
            self.points[i] = (self.points[i][0] + dx, self.points[i][1] + dy)
        # 경계 상자도 함께 이동
        self.min_x += dx
        self.max_x += dx
        self.min_y += dy
        self.max_y += dy
        self.update_path_elements() # Path 요소 업데이트

    # 획의 크기를 조정하는 함수
    def scale(self, factor, center_x, center_y):
        if not self.points:
            return
        
        new_points = []
        for x, y in self.points:
            # 중심점을 기준으로 점들을 확대/축소
            new_x = center_x + (x - center_x) * factor
            new_y = center_y + (y - center_y) * factor
            new_points.append((new_x, new_y))
        
        self.points = new_points
        
        # 크기 변경 후 경계 상자 다시 계산
        self.min_x = float('inf')
        self.max_x = float('-inf')
        self.min_y = float('inf')
        self.max_y = float('-inf')
        for x, y in self.points:
            self.min_x = min(self.min_x, x)
            self.max_x = max(self.max_x, x)
            self.min_y = min(self.min_y, y)
            self.max_y = max(self.max_y, y)
            
        self.update_path_elements() # Path 요소 업데이트


def main(page: ft.Page):
    page.title = "Flet 프리핸드 노트 앱"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.window_width = 800
    page.window_height = 600

    all_strokes = [] # 캔버스에 그려진 모든 획들을 저장하는 리스트
    current_stroke = None # 현재 그려지고 있는 획 (그리기 모드에서)
    selected_stroke = None # 현재 선택된 획 (선택/조작 모드에서)
    
    current_mode_type = "draw" # "draw", "select", "erase"

    drawing_paint_color = ft.Colors.BLACK # 현재 그리기 색상
    drawing_stroke_width = 3.0 # 현재 그리기 획 고정 두께 (압력 감지 비활성 시)

    # 압력 감지 시뮬레이션을 위한 변수
    is_pressure_sensitive = False
    last_pan_time = None
    last_pan_x = None
    last_pan_y = None

    # 압력 감지 시뮬레이션 관련 상수 및 획 두께 상한
    MIN_SPEED_THRESHOLD = 50.0  # 느린 움직임 (두꺼운 선)
    MAX_SPEED_THRESHOLD = 500.0 # 빠른 움직임 (얇은 선)
    MIN_DISPLAY_WIDTH = 1.0     # 최소 획 두께
    MAX_STROKE_WIDTH_CAP = 20.0 # 슬라이더로 조절 가능한 최대 두께의 상한선

    # 캔버스에 있는 모든 획들을 다시 그리고 UI를 업데이트하는 함수
    def update_canvas_shapes():
        canvas.shapes.clear() # 캔버스에서 모든 기존 획 제거
        for stroke in all_strokes:
            stroke.update_path_elements() # 각 획의 Path 요소와 선택 상태 업데이트
            canvas.shapes.append(stroke.path) # 캔버스에 획 추가
        canvas.update() # 캔버스 UI 업데이트 요청

    # 획을 선택하는 함수
    def select_stroke(event_x, event_y):
        nonlocal selected_stroke
        
        # 현재 선택된 획이 있다면 선택 해제
        if selected_stroke:
            selected_stroke.is_selected = False
            selected_stroke = None
        
        # 모든 획을 역순으로 순회하며 (가장 위에 그려진 획부터) 충돌 검사
        for stroke in reversed(all_strokes):
            if stroke.is_hit(event_x, event_y):
                stroke.is_selected = True # 획 선택
                selected_stroke = stroke
                break # 하나만 선택하고 종료
        update_canvas_shapes() # 선택 변경 사항을 반영하여 캔버스 다시 그리기
        update_buttons_state() # 버튼 상태 업데이트

    # Pan (드래그) 시작 이벤트 핸들러
    def handle_pan_start(e: ft.DragStartEvent):
        nonlocal current_stroke, selected_stroke, last_pan_time, last_pan_x, last_pan_y

        if current_mode_type == "draw":
            # 그리기 모드일 경우: 새로운 획 시작
            # 압력 감지 활성화 여부에 따라 초기 획 두께 설정
            initial_stroke_width = stroke_width_slider.value if is_pressure_sensitive else drawing_stroke_width
            current_stroke = Stroke(drawing_paint_color, initial_stroke_width)
            current_stroke.add_point(e.local_x, e.local_y)
            canvas.shapes.append(current_stroke.path) # 캔버스에 즉시 추가
            all_strokes.append(current_stroke) # 모든 획 목록에 추가

            # 압력 감지를 위한 초기 시간 및 위치 기록
            if is_pressure_sensitive:
                last_pan_time = time.time()
                last_pan_x = e.local_x
                last_pan_y = e.local_y
            
            canvas.update()
        elif current_mode_type == "select":
            # 선택/조작 모드일 경우: 획 선택 또는 드래그 시작
            select_stroke(e.local_x, e.local_y)
            if selected_stroke:
                selected_stroke.drag_start_x = e.local_x
                selected_stroke.drag_start_y = e.local_y
        elif current_mode_type == "erase":
            # 지우개 모드일 경우: 탭 시 바로 삭제 시도
            stroke_to_remove = None
            for stroke in reversed(all_strokes):
                if stroke.is_hit(e.local_x, e.local_y):
                    stroke_to_remove = stroke
                    break
            if stroke_to_remove:
                all_strokes.remove(stroke_to_remove)
                if selected_stroke == stroke_to_remove:
                    selected_stroke.is_selected = False
                    selected_stroke = None
                update_canvas_shapes()
                update_buttons_state() # 버튼 상태 업데이트

    # Pan (드래그) 업데이트 이벤트 핸들러
    def handle_pan_update(e: ft.DragUpdateEvent):
        nonlocal current_stroke, last_pan_time, last_pan_x, last_pan_y, selected_stroke
        
        if current_mode_type == "draw" and current_stroke:
            # 그리기 모드
            current_stroke.add_point(e.local_x, e.local_y)

            if is_pressure_sensitive and last_pan_time is not None:
                current_time = time.time()
                dt = current_time - last_pan_time

                if dt > 0:
                    distance = math.sqrt((e.local_x - last_pan_x)**2 + (e.local_y - last_pan_y)**2)
                    speed = distance / dt

                    # 속도에 따라 획 두께 매핑 (느릴수록 두껍게, 빠를수록 얇게)
                    # 정규화된 속도 (0.0 ~ 1.0)
                    normalized_speed = (speed - MIN_SPEED_THRESHOLD) / (MAX_SPEED_THRESHOLD - MIN_SPEED_THRESHOLD)
                    clamped_normalized_speed = max(0.0, min(1.0, normalized_speed))

                    effective_width = stroke_width_slider.value - (clamped_normalized_speed * (stroke_width_slider.value - MIN_DISPLAY_WIDTH))
                    
                    current_stroke.path.paint.stroke_width = max(MIN_DISPLAY_WIDTH, effective_width)
                    current_stroke.width = max(MIN_DISPLAY_WIDTH, effective_width) # Stroke 객체에도 업데이트
                
                last_pan_time = current_time
                last_pan_x = e.local_x
                last_pan_y = e.local_y

            canvas.update()

        elif current_mode_type == "select" and selected_stroke and hasattr(selected_stroke, 'drag_start_x'):
            # 선택/조작 모드
            dx = e.local_x - selected_stroke.drag_start_x
            dy = e.local_y - selected_stroke.drag_start_y
            selected_stroke.translate(dx, dy)
            selected_stroke.drag_start_x = e.local_x
            selected_stroke.drag_start_y = e.local_y
            canvas.update()
        
        elif current_mode_type == "erase":
            # 지우개 모드: 드래그하는 동안 획 지속적으로 삭제
            strokes_to_remove_in_update = []
            for stroke in reversed(all_strokes):
                if stroke.is_hit(e.local_x, e.local_y):
                    strokes_to_remove_in_update.append(stroke)
            
            # 중복 제거 및 실제로 목록에서 제거
            for stroke_to_remove in strokes_to_remove_in_update:
                if stroke_to_remove in all_strokes: # 이미 제거되지 않았는지 다시 확인
                    all_strokes.remove(stroke_to_remove)
                    if selected_stroke == stroke_to_remove: # 지워진 획이 선택되어 있었다면 선택 해제
                        selected_stroke.is_selected = False
                        selected_stroke = None
            
            if strokes_to_remove_in_update: # 변경 사항이 있다면 캔버스 업데이트
                update_canvas_shapes()
                update_buttons_state() # 버튼 상태 업데이트

    # Pan (드래그) 종료 이벤트 핸들러
    def handle_pan_end(e: ft.DragEndEvent):
        nonlocal current_stroke, last_pan_time, last_pan_x, last_pan_y
        if current_mode_type == "draw" and current_stroke:
            # 그리기 모드 종료
            current_stroke = None
            last_pan_time = None
            last_pan_x = None
            last_pan_y = None
            canvas.update()
        elif current_mode_type == "select" and selected_stroke and hasattr(selected_stroke, 'drag_start_x'):
            # 선택/조작 모드 드래그 종료
            del selected_stroke.drag_start_x
            del selected_stroke.drag_start_y
            canvas.update()
        # 지우개 모드는 특별한 종료 로직 없음 (연속 동작)


    # 모드 설정 함수 (모든 모드 버튼이 호출)
    def set_mode(mode: str):
        nonlocal current_mode_type, selected_stroke
        
        # 현재 모드와 같은 모드를 선택하면 아무것도 하지 않음
        if current_mode_type == mode:
            return

        current_mode_type = mode

        # 다른 모드로 전환 시 현재 선택된 획이 있다면 선택 해제
        if selected_stroke:
            selected_stroke.is_selected = False
            selected_stroke = None
            update_canvas_shapes() # 선택 해제 반영

        # 모든 모드 버튼의 텍스트/아이콘/스타일 업데이트
        # 현재 활성화된 모드 버튼만 `FilledButton`으로 표시
        draw_mode_button.style = ft.ButtonStyle(
            bgcolor=ft.Colors.BLUE_GREY_100 if current_mode_type != "draw" else ft.Colors.BLUE_200,
            color=ft.Colors.BLACK if current_mode_type != "draw" else ft.Colors.WHITE
        )
        select_mode_button.style = ft.ButtonStyle(
            bgcolor=ft.Colors.BLUE_GREY_100 if current_mode_type != "select" else ft.Colors.BLUE_200,
            color=ft.Colors.BLACK if current_mode_type != "select" else ft.Colors.WHITE
        )
        eraser_mode_button.style = ft.ButtonStyle(
            bgcolor=ft.Colors.BLUE_GREY_100 if current_mode_type != "erase" else ft.Colors.BLUE_200,
            color=ft.Colors.BLACK if current_mode_type != "erase" else ft.Colors.WHITE
        )

        update_buttons_state() # 버튼 활성화/비활성화 상태 업데이트
        page.update()

    # 모드 버튼 클릭 핸들러
    def activate_draw_mode(e):
        set_mode("draw")

    def activate_select_mode(e):
        set_mode("select")

    def activate_erase_mode(e):
        set_mode("erase")


    # 선택된 획 삭제 버튼 클릭 핸들러
    def delete_selected_stroke(e):
        nonlocal selected_stroke
        if selected_stroke:
            all_strokes.remove(selected_stroke) # 모든 획 목록에서 제거
            selected_stroke = None # 선택된 획 해제
            update_canvas_shapes() # 캔버스 다시 그리기 (삭제 반영)
            update_buttons_state() # 버튼 상태 업데이트
            page.update()

    # 선택된 획 크기 조절 함수
    def scale_selected_stroke(e, factor):
        if selected_stroke and selected_stroke.points:
            # 획의 경계 상자를 기준으로 중심점 계산 (확대/축소 기준점)
            center_x = (selected_stroke.min_x + selected_stroke.max_x) / 2
            center_y = (selected_stroke.min_y + selected_stroke.max_y) / 2
            
            selected_stroke.scale(factor, center_x, center_y) # 획 크기 조정
            update_canvas_shapes() # 캔버스 다시 그리기
            page.update()

    # 조작 버튼(삭제, 확대, 축소)의 활성화/비활성화 상태 업데이트
    def update_buttons_state():
        # 선택/조작 버튼은 "select" 모드에서 획이 선택되었을 때만 활성화
        is_selected_and_manipulate = (selected_stroke is not None) and (current_mode_type == "select")
        delete_button.disabled = not is_selected_and_manipulate
        scale_up_button.disabled = not is_selected_and_manipulate
        scale_down_button.disabled = not is_selected_and_manipulate

        # 그리기 관련 컨트롤의 가시성 (그리기 모드일 때만 보임)
        drawing_controls_row.visible = (current_mode_type == "draw")
        
        # 슬라이더 텍스트 변경
        if pressure_sensitivity_switch.value and current_mode_type == "draw":
            stroke_width_text.value = "최대 두께:"
        else:
            stroke_width_text.value = "두께:"
        
        # 슬라이더 값 동기화
        current_slider_value = drawing_stroke_width
        if pressure_sensitivity_switch.value and current_mode_type == "draw":
            # 압력 감지 모드 활성 시, 슬라이더는 MAX_STROKE_WIDTH_CAP을 최대값으로 사용하며, 현재 값은 유저가 조절한 값
            current_slider_value = stroke_width_slider.value # 슬라이더의 현재 값을 유지
        else:
            # 압력 감지 비활성 시, 슬라이더는 drawing_stroke_width를 나타내도록 함
            current_slider_value = drawing_stroke_width
        
        # 슬라이더 값이 min/max 범위를 벗어나지 않도록 클램핑
        stroke_width_slider.value = max(stroke_width_slider.min, min(stroke_width_slider.max, current_slider_value))
        stroke_width_slider.label = f"{stroke_width_slider.value:.1f}"
        
        # 개별 컨트롤 업데이트
        stroke_width_slider.update()
        stroke_width_text.update()
        drawing_controls_row.update()
        delete_button.update()
        scale_up_button.update()
        scale_down_button.update()

        page.update()

    # 그리기 색상 변경 함수
    def set_drawing_color(color):
        nonlocal drawing_paint_color
        drawing_paint_color = color
        page.update()

    # 그리기 획 두께 변경 함수 (슬라이더)
    def change_stroke_width(e):
        nonlocal drawing_stroke_width
        # 슬라이더 값은 float으로 받음
        new_width = float(e.control.value)
        if pressure_sensitivity_switch.value and current_mode_type == "draw":
            # 압력 감지 활성 시, 슬라이더는 최대 두께를 제어. MAX_STROKE_WIDTH_CAP은 슬라이더의 물리적인 최대값을 의미
            # MAX_DISPLAY_WIDTH는 실제 내부에서 사용될 속도 기반 획의 최대 두께
            # 이 함수의 역할은 슬라이더 값을 `drawing_stroke_width` 또는 `MAX_STROKE_WIDTH_CAP`에 동기화하는 것이 아니라,
            # 슬라이더의 현재 값을 해당 변수에 반영하는 것임.
            # handle_pan_update에서 stroke_width_slider.value를 직접 사용하므로 여기서는 특별히 변수 업데이트 불필요.
            pass 
        else:
            # 압력 감지 비활성 시, 슬라이더는 고정 두께를 제어
            drawing_stroke_width = new_width
        update_buttons_state() # 슬라이더 라벨 및 상태 업데이트를 위해 호출
        page.update()

    # 압력 감지 스위치 토글 핸들러
    def toggle_pressure_sensitivity(e):
        nonlocal is_pressure_sensitive
        is_pressure_sensitive = e.control.value
        update_buttons_state() # 스위치 상태 변경 시 버튼/슬라이더 상태 업데이트

    # 캔버스 설정
    canvas = Canvas(
        [], # 초기 획 목록은 비어 있음
        expand=True, # 캔버스가 사용 가능한 모든 공간을 채우도록 확장
        # bgcolor=ft.Colors.GREY_100, # 캔버스 배경색
        # 제스처 감지기 이벤트 핸들러 연결
        content=ft.Container(
            ft.GestureDetector(
                on_pan_start=handle_pan_start,
                on_pan_update=handle_pan_update,
                on_pan_end=handle_pan_end,
                drag_interval=10,
                on_tap_down=lambda e: select_stroke(e.local_x, e.local_y) if current_mode_type == "select" else None,
            ),
            border_radius=5,
            border=ft.border.all(2, ft.Colors.BLACK38),
        ),

        
    )

    # UI 컨트롤 요소들 정의
    # 모드 선택 버튼 (스타일 초기화)
    draw_mode_button = ft.FilledButton(
        text="모드: 그리기",
        icon=ft.Icons.DRAW,
        on_click=activate_draw_mode,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.BLUE_200, # 초기 활성 색상
            color=ft.Colors.WHITE
        )
    )
    select_mode_button = ft.FilledButton(
        text="선택/조작",
        icon=ft.Icons.TOUCH_APP,
        on_click=activate_select_mode,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.BLUE_GREY_100, # 초기 비활성 색상
            color=ft.Colors.BLACK
        )
    )
    eraser_mode_button = ft.FilledButton(
        text="지우개",
        icon=ft.Icons.SQUARE,
        on_click=activate_erase_mode,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.BLUE_GREY_100, # 초기 비활성 색상
            color=ft.Colors.BLACK
        )
    )

    delete_button = ft.IconButton(
        icon=ft.Icons.DELETE,
        tooltip="선택한 획 삭제",
        on_click=delete_selected_stroke,
        disabled=True, # 초기에는 비활성화
    )
    scale_up_button = ft.IconButton(
        icon=ft.Icons.ZOOM_IN,
        tooltip="선택한 획 확대",
        on_click=lambda e: scale_selected_stroke(e, 1.1), # 10% 확대
        disabled=True, # 초기에는 비활성화
    )
    scale_down_button = ft.IconButton(
        icon=ft.Icons.ZOOM_OUT,
        tooltip="선택한 획 축소",
        on_click=lambda e: scale_selected_stroke(e, 0.9), # 10% 축소
        disabled=True, # 초기에는 비활성화
    )

    # 색상 팔레트 버튼들
    color_buttons = ft.Row(spacing=2) # 버튼 간 간격 조정
    colors = [ft.Colors.BLACK, ft.Colors.RED, ft.Colors.GREEN, ft.Colors.BLUE, ft.Colors.YELLOW, ft.Colors.PURPLE]
    for color in colors:
        color_buttons.controls.append(
            ft.IconButton(
                icon=ft.Icons.CIRCLE,
                icon_color=color,
                on_click=lambda e, c=color: set_drawing_color(c),
                tooltip=f"그리기 색상: {color}",
            )
        )
    
    # 획 두께 슬라이더 및 라벨
    stroke_width_text = ft.Text("두께:", weight=ft.FontWeight.BOLD)
    stroke_width_slider = ft.Slider(
        min=MIN_DISPLAY_WIDTH, max=MAX_STROKE_WIDTH_CAP, # 슬라이더의 최대값을 상수화
        divisions=int((MAX_STROKE_WIDTH_CAP - MIN_DISPLAY_WIDTH) * 2), # 정수 간격으로 세분화
        value=drawing_stroke_width, label="{value:.1f}", # 소수점 한 자리까지 표시
        on_change=change_stroke_width,
        width=150,
        tooltip="그리기 획 두께"
    )

    # 압력 감지 스위치
    pressure_sensitivity_switch = ft.Switch(
        label="압력 감지 (속도 기반)",
        value=is_pressure_sensitive,
        on_change=toggle_pressure_sensitivity,
        tooltip="그리기 속도에 따라 획 두께 조절"
    )

    # 그리기 모드일 때만 보이는 컨트롤 그룹
    drawing_controls_row = ft.Row(
        [
            ft.VerticalDivider(),
            stroke_width_text,
            stroke_width_slider,
            ft.VerticalDivider(),
            pressure_sensitivity_switch,
        ],
        alignment=ft.MainAxisAlignment.START,
        spacing=10,
        wrap=True,
        visible=True # 초기에는 그리기 모드이므로 보임
    )

    # UI 레이아웃 구성
    page.add(
        ft.Column(
            [
                # 상단 제어판 (모드 선택, 색상, 두께, 압력 감지, 조작 버튼)
                ft.Card( # 깔끔한 UI를 위해 Card로 묶음
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Row( # 모드 선택 및 색상
                                    [
                                        draw_mode_button,
                                        select_mode_button,
                                        eraser_mode_button, # 지우개 버튼 추가
                                        ft.VerticalDivider(),
                                        ft.Text("색상:", weight=ft.FontWeight.BOLD),
                                        color_buttons,
                                    ],
                                    alignment=ft.MainAxisAlignment.START,
                                    spacing=10,
                                    wrap=True
                                ),
                                ft.Divider(height=5, color=ft.Colors.TRANSPARENT), # 간격
                                ft.Row( # 그리기 컨트롤 및 조작 버튼
                                    [
                                        drawing_controls_row, # 그리기 관련 컨트롤 (가시성 동적 조절)
                                        ft.VerticalDivider(),
                                        delete_button,
                                        scale_up_button,
                                        scale_down_button,
                                    ],
                                    alignment=ft.MainAxisAlignment.START,
                                    spacing=10,
                                    wrap=True
                                ),
                            ],
                            spacing=5,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=10,
                    ),
                    margin=10,
                ),
                # 캔버스 영역
                ft.Container(
                    content=canvas,
                    expand=True, # 부모 컬럼에 맞게 확장
                    border=ft.border.all(1, ft.Colors.GREY_400), # 테두리
                    border_radius=ft.border_radius.all(10), # 둥근 모서리
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS, # 테두리에 맞춰 콘텐츠 자르기
                    margin=ft.margin.only(left=10, right=10, bottom=10) # 마진 추가
                ),
            ],
            expand=True, # 페이지에 맞게 확장
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, # 가로 중앙 정렬
        )
    )
    # 초기 상태 업데이트 호출하여 모드 버튼 스타일, 버튼 비활성화 상태 등을 설정
    update_buttons_state() 
    # 초기 모드 설정 (draw 모드 활성화)
    set_mode("draw")
    page.add(ft.ResponsiveRow([
    ft.Column(col=6, controls=[ft.Text("Column 1")]),
    ft.Column(col=6, controls=[ft.Text("Column 2")])
]))
# Flet 앱 실행
ft.app(target=main)
