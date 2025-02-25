import pygame
import math
import sys
import webbrowser  # To open the URL when clicked

# Screen settings
WIDTH, HEIGHT = 800, 600
FPS = 60

# Hexagon settings
HEXAGON_CENTER = (WIDTH // 2, HEIGHT // 2)
HEXAGON_RADIUS = 200
hexagon_rotation = 0.0
hexagon_angular_velocity = 0.01  # initial angular velocity (radians per frame)
ANGULAR_ACCELERATION = 0.002     # angular acceleration per frame when key is pressed

# Ball settings
ball_pos = pygame.math.Vector2(WIDTH // 2, HEIGHT // 2)
ball_velocity = pygame.math.Vector2(3, -2)  # initial velocity (pixels per frame)
ball_radius = 15
GRAVITY = 0.2
AIR_FRICTION = 0.999  # simulates air resistance
COEFFICIENT_RESTITUTION = 0.9  # bounciness factor

# Color definitions
BACKGROUND_COLOR = (20, 20, 30)
HEXAGON_COLOR = (100, 150, 200)
HEXAGON_OUTLINE_COLOR = (150, 200, 250)
BALL_COLOR = (220, 60, 60)
TEXT_COLOR = (255, 255, 255)
HIGHLIGHT_COLOR = (255, 200, 0)

def get_hexagon_vertices(center, radius, rotation):
    """Return a list of six vertices for a regular hexagon rotated by 'rotation'."""
    vertices = []
    cx, cy = center
    # Offset by pi/6 for a flat top appearance
    for i in range(6):
        angle = rotation + math.pi/6 + i * (math.pi/3)
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        vertices.append(pygame.math.Vector2(x, y))
    return vertices

def closest_point_on_segment(point, seg_a, seg_b):
    """Return the closest point on the segment from seg_a to seg_b relative to point."""
    ap = point - seg_a
    ab = seg_b - seg_a
    denom = ab.length_squared()
    if denom < 0.0001:
        return pygame.math.Vector2(seg_a)
    t = ap.dot(ab) / denom
    t = max(0, min(1, t))
    return seg_a + ab * t

def wall_velocity_at_point(point, center, angular_velocity):
    """Compute the tangential (linear) velocity at a point on a rotating body (v = ω × r)."""
    r = point - pygame.math.Vector2(center)
    perp = pygame.math.Vector2(-r.y, r.x)
    return perp * angular_velocity

def handle_collision(ball_pos, ball_velocity, ball_radius, hexagon_vertices, hexagon_center, angular_velocity):
    """
    Check and resolve collisions between the ball and each edge of the hexagon.
    The ball's velocity is adjusted based on the relative motion of the wall.
    """
    collision_occurred = False
    for i in range(len(hexagon_vertices)):
        p1 = hexagon_vertices[i]
        p2 = hexagon_vertices[(i + 1) % len(hexagon_vertices)]
        closest = closest_point_on_segment(ball_pos, p1, p2)
        dist_vector = ball_pos - closest
        distance = dist_vector.length()
        if distance < ball_radius:
            collision_occurred = True
            if distance > 0.0001:
                normal = dist_vector / distance
            else:
                edge = p2 - p1
                edge_length = edge.length()
                if edge_length > 0.0001:
                    normal = pygame.math.Vector2(-edge.y / edge_length, edge.x / edge_length)
                else:
                    normal = pygame.math.Vector2(0, 1)
            penetration_depth = ball_radius - distance
            ball_pos += normal * penetration_depth
            wall_vel = wall_velocity_at_point(closest, hexagon_center, angular_velocity)
            rel_vel = ball_velocity - wall_vel
            if rel_vel.dot(normal) < 0:
                energy_factor = 1.0 + abs(angular_velocity) * 5
                bounce_coef = COEFFICIENT_RESTITUTION * energy_factor
                rel_vel = rel_vel - (1 + bounce_coef) * rel_vel.dot(normal) * normal
                ball_velocity = rel_vel + wall_vel
                ball_velocity += pygame.math.Vector2(
                    (hash(str(ball_pos.x)) % 100) / 2000.0,
                    (hash(str(ball_pos.y)) % 100) / 2000.0
                )
    return ball_pos, ball_velocity, collision_occurred

def point_in_polygon(point, vertices):
    """
    Check if a point is inside a convex polygon using the winding number algorithm.
    """
    winding_number = 0
    for i in range(len(vertices)):
        p1 = vertices[i]
        p2 = vertices[(i + 1) % len(vertices)]
        if p1.y <= point.y:
            if p2.y > point.y and (p2 - p1).cross(point - p1) > 0:
                winding_number += 1
        else:
            if p2.y <= point.y and (p2 - p1).cross(point - p1) < 0:
                winding_number -= 1
    return winding_number != 0

def ensure_ball_inside(ball_pos, ball_velocity, ball_radius, hex_vertices):
    """
    If the ball's center is outside the hexagon, reposition it at the boundary
    and adjust its velocity by reflecting along the inward normal.
    """
    if point_in_polygon(ball_pos, hex_vertices):
        return ball_pos, ball_velocity, False
    min_distance = float('inf')
    best_closest = None
    best_normal = None
    for i in range(len(hex_vertices)):
        p1 = hex_vertices[i]
        p2 = hex_vertices[(i + 1) % len(hex_vertices)]
        closest = closest_point_on_segment(ball_pos, p1, p2)
        dist_vector = ball_pos - closest
        distance = dist_vector.length()
        if distance < min_distance:
            min_distance = distance
            if distance > 0.0001:
                best_normal = dist_vector / distance
            else:
                edge = p2 - p1
                edge_length = edge.length()
                if edge_length > 0.0001:
                    best_normal = pygame.math.Vector2(-edge.y / edge_length, edge.x / edge_length)
                else:
                    best_normal = pygame.math.Vector2(0, 1)
            best_closest = closest
    inward_normal = -best_normal
    ball_pos = best_closest + inward_normal * ball_radius
    vel_dot_inward = ball_velocity.dot(inward_normal)
    if vel_dot_inward < 0:
        ball_velocity = ball_velocity - (1 + COEFFICIENT_RESTITUTION) * vel_dot_inward * inward_normal
        return ball_pos, ball_velocity, True
    return ball_pos, ball_velocity, False

def draw_trail(screen, trail_points, trail_width=2):
    """Draw a fading trail behind the ball."""
    if len(trail_points) < 2:
        return
    for i in range(1, len(trail_points)):
        alpha = int(150 * (i / len(trail_points)))
        color = (BALL_COLOR[0], BALL_COLOR[1], BALL_COLOR[2], alpha)
        pygame.draw.line(
            screen, 
            color, 
            (trail_points[i-1].x, trail_points[i-1].y),
            (trail_points[i].x, trail_points[i].y), 
            max(1, int(trail_width * i / len(trail_points)))
        )

def format_speed(speed):
    """Format speed values with appropriate precision based on magnitude."""
    if speed < 10:
        return f"{speed:.2f}"
    elif speed < 100:
        return f"{speed:.1f}"
    else:
        return f"{int(speed)}"

def main():
    global hexagon_rotation, ball_pos, ball_velocity, hexagon_angular_velocity

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Bouncing Ball in a Spinning Hexagon")
    clock = pygame.time.Clock()

    # Create a surface for the trail with alpha channel
    trail_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    
    # Initialize fonts for displaying text
    font = pygame.font.SysFont("Arial", 24)
    big_font = pygame.font.SysFont("Arial", 36)

    # Track metrics
    max_ball_speed = 0.0
    collision_count = 0
    last_speeds = []
    speed_history = []
    
    # Trail points for ball
    trail_points = []
    MAX_TRAIL_LENGTH = 20
    
    # Game state
    game_paused = False
    show_instructions = True
    instruction_timer = 5 * FPS
    frame_counter = 0
    show_detailed_stats = False

    try:
        pygame.mixer.init()
        collision_sound = pygame.mixer.Sound("collision.wav")
        collision_sound.set_volume(0.3)
    except:
        collision_sound = None

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        frame_counter += 1

        # Process events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_p:
                    game_paused = not game_paused
                elif event.key == pygame.K_h:
                    show_instructions = not show_instructions
                elif event.key == pygame.K_r:
                    ball_pos = pygame.math.Vector2(WIDTH // 2, HEIGHT // 2)
                    ball_velocity = pygame.math.Vector2(3, -2)
                    hexagon_rotation = 0.0
                    hexagon_angular_velocity = 0.01
                    max_ball_speed = 0.0
                    collision_count = 0
                    last_speeds = []
                    speed_history = []
                    trail_points = []
                elif event.key == pygame.K_s:
                    show_detailed_stats = not show_detailed_stats
            # Check for mouse clicks for the clickable label
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Calculate the clickable label rect for "@eizenmanroee"
                clickable_text = "@eizenmanroee"
                text_width, text_height = font.size(clickable_text)
                clickable_label_rect = pygame.Rect(0, 0, text_width, text_height)
                clickable_label_rect.midbottom = (WIDTH // 2, HEIGHT - 10)
                if clickable_label_rect.collidepoint(event.pos):
                    webbrowser.open("https://x.com/eizenmanroee")

        if instruction_timer > 0:
            instruction_timer -= 1
            if instruction_timer == 0:
                show_instructions = False

        if not game_paused:
            keys = pygame.key.get_pressed()
            # Space bar immediately stops the hexagon.
            if keys[pygame.K_SPACE]:
                hexagon_angular_velocity = 0
            # Down arrow gradually decreases the spin speed.
            elif keys[pygame.K_DOWN]:
                hexagon_angular_velocity *= 0.95
                if abs(hexagon_angular_velocity) < 0.001:
                    hexagon_angular_velocity = 0
            else:
                if keys[pygame.K_LEFT]:
                    hexagon_angular_velocity -= ANGULAR_ACCELERATION
                if keys[pygame.K_RIGHT]:
                    hexagon_angular_velocity += ANGULAR_ACCELERATION

            hexagon_rotation += hexagon_angular_velocity

            ball_velocity.y += GRAVITY
            ball_velocity *= AIR_FRICTION
            ball_pos += ball_velocity

            if len(trail_points) >= MAX_TRAIL_LENGTH:
                trail_points.pop(0)
            trail_points.append(pygame.math.Vector2(ball_pos))

            hex_vertices = get_hexagon_vertices(HEXAGON_CENTER, HEXAGON_RADIUS, hexagon_rotation)

            collision_result = handle_collision(ball_pos, ball_velocity, ball_radius, hex_vertices, HEXAGON_CENTER, hexagon_angular_velocity)
            ball_pos, ball_velocity, collision_happened = collision_result
            if collision_happened:
                collision_count += 1
                if collision_sound:
                    pitch = min(2.0, max(0.7, ball_velocity.length() / 10))
                    collision_sound.set_volume(min(1.0, ball_velocity.length() / 20))
                    collision_sound.play()

            containment_result = ensure_ball_inside(ball_pos, ball_velocity, ball_radius, hex_vertices)
            ball_pos, ball_velocity, containment_collision = containment_result
            if containment_collision:
                collision_count += 1

            current_ball_speed = ball_velocity.length()
            last_speeds.append(current_ball_speed)
            if len(last_speeds) > 10:
                last_speeds.pop(0)
            if frame_counter % 10 == 0:
                speed_history.append(current_ball_speed)
                if len(speed_history) > 30:
                    speed_history.pop(0)
            if current_ball_speed > max_ball_speed:
                max_ball_speed = current_ball_speed

        screen.fill(BACKGROUND_COLOR)

        for i in range(1, len(trail_points)):
            progress = i / len(trail_points)
            alpha = int(150 * progress)
            width = int(1 + 5 * progress)
            pygame.draw.line(
                screen,
                (*BALL_COLOR[:3], alpha),
                (int(trail_points[i-1].x), int(trail_points[i-1].y)),
                (int(trail_points[i].x), int(trail_points[i].y)),
                width
            )

        hex_points = [(v.x, v.y) for v in hex_vertices]
        pygame.draw.polygon(screen, HEXAGON_COLOR, hex_points)
        pygame.draw.polygon(screen, HEXAGON_OUTLINE_COLOR, hex_points, 3)

        pygame.draw.circle(screen, BALL_COLOR, (int(ball_pos.x), int(ball_pos.y)), ball_radius)
        highlight_pos = (int(ball_pos.x - ball_radius/3), int(ball_pos.y - ball_radius/3))
        pygame.draw.circle(screen, (255, 255, 255), highlight_pos, ball_radius//3)

        avg_speed = sum(last_speeds) / max(1, len(last_speeds))
        is_near_max = current_ball_speed > max_ball_speed * 0.9
        
        # Convert hexagon angular speed to linear speed (pixels per frame)
        hex_linear_speed = abs(hexagon_angular_velocity) * HEXAGON_RADIUS
        hex_speed_text = font.render(f"Hex Speed: {format_speed(hex_linear_speed)}", True, TEXT_COLOR)
        ball_speed_text = font.render(f"Ball Speed: {format_speed(avg_speed)}", True, 
                                      HIGHLIGHT_COLOR if is_near_max else TEXT_COLOR)
        max_speed_text = font.render(f"Max Speed: {format_speed(max_ball_speed)}", True, HIGHLIGHT_COLOR)
        
        hex_speed_rect = hex_speed_text.get_rect(topright=(WIDTH - 10, 10))
        ball_speed_rect = ball_speed_text.get_rect(topright=(WIDTH - 10, hex_speed_rect.bottom + 5))
        max_speed_rect = max_speed_text.get_rect(topright=(WIDTH - 10, ball_speed_rect.bottom + 5))
        
        screen.blit(hex_speed_text, hex_speed_rect)
        screen.blit(ball_speed_text, ball_speed_rect)
        screen.blit(max_speed_text, max_speed_rect)

        if show_detailed_stats:
            collision_text = font.render(f"Collisions: {collision_count}", True, TEXT_COLOR)
            if speed_history:
                avg_history = sum(speed_history) / len(speed_history)
                min_history = min(speed_history)
                history_text = font.render(f"Avg: {format_speed(avg_history)} | Min: {format_speed(min_history)}", True, TEXT_COLOR)
                acceleration = 0
                if len(speed_history) >= 2:
                    acceleration = (speed_history[-1] - speed_history[-2]) / 10 * FPS
                accel_text = font.render(f"Acceleration: {'+' if acceleration >= 0 else ''}{acceleration:.2f}/s", True, TEXT_COLOR if abs(acceleration) < 1 else HIGHLIGHT_COLOR)
                
                collision_rect = collision_text.get_rect(topleft=(10, 10))
                history_rect = history_text.get_rect(topleft=(10, collision_rect.bottom + 5))
                accel_rect = accel_text.get_rect(topleft=(10, history_rect.bottom + 5))
                
                screen.blit(collision_text, collision_rect)
                screen.blit(history_text, history_rect)
                screen.blit(accel_text, accel_rect)
            else:
                collision_rect = collision_text.get_rect(topleft=(10, 10))
                screen.blit(collision_text, collision_rect)
        else:
            collision_text = font.render(f"Collisions: {collision_count}", True, TEXT_COLOR)
            collision_rect = collision_text.get_rect(topleft=(10, 10))
            screen.blit(collision_text, collision_rect)

        if game_paused:
            pause_text = big_font.render("PAUSED", True, TEXT_COLOR)
            pause_rect = pause_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 50))
            screen.blit(pause_text, pause_rect)

        if show_instructions:
            instructions = [
                "Left/Right Arrow: Spin Hexagon | Down: Decrease Speed | Space: Immediate Stop",
                "P: Pause | H: Toggle Help | R: Reset | S: Detailed Stats"
            ]
            instruction_y = HEIGHT - 10 - (len(instructions) * 30)
            for i, text in enumerate(instructions):
                instr_text = font.render(text, True, TEXT_COLOR)
                instr_rect = instr_text.get_rect(midbottom=(WIDTH // 2, instruction_y + (i * 30)))
                screen.blit(instr_text, instr_rect)

        # Draw the clickable label at the bottom center
        clickable_text = "@eizenmanroee"
        clickable_label = font.render(clickable_text, True, TEXT_COLOR)
        clickable_rect = clickable_label.get_rect(midbottom=(WIDTH // 2, HEIGHT - 10))
        screen.blit(clickable_label, clickable_rect)

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    main()
