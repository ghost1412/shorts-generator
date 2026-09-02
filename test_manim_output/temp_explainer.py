from manim import *

class ExplainerScene(Scene):
    def construct(self):
        # Title
        title = Text("Pythagorean Theorem", font_size=40, color=BLUE)
        title.to_edge(UP, buff=0.5)
        
        # Triangle coordinates (3-4-5 triangle scaled)
        A = [-1.2, -1.2, 0]
        B = [0.6, -1.2, 0]
        C = [0.6, 1.2, 0]
        
        triangle = Polygon(A, B, C, color=WHITE, stroke_width=4)
        right_angle = Polygon([0.4, -1.2, 0], [0.4, -1.0, 0], [0.6, -1.0, 0], color=YELLOW, stroke_width=2)
        
        # Labels
        label_a = Text("a = 3", font_size=28, color=RED)
        label_a.next_to(triangle, DOWN, buff=0.2)
        
        label_b = Text("b = 4", font_size=28, color=GREEN)
        label_b.next_to(triangle, RIGHT, buff=0.2)
        
        # Position label c along the hypotenuse
        label_c = Text("c = 5", font_size=28, color=ORANGE)
        label_c.move_to([-0.3, 0, 0]).shift([-0.5, 0.5, 0])
        
        triangle_group = VGroup(triangle, right_angle, label_a, label_b, label_c)
        triangle_group.shift(RIGHT * 2.5 + DOWN * 0.5)
        
        # Math steps on the left
        formula = Text("a² + b² = c²", font_size=36, color=YELLOW)
        step1 = Text("3² + 4² = c²", font_size=30)
        step2 = Text("9 + 16 = c²", font_size=30)
        step3 = Text("25 = c²", font_size=30)
        step4 = Text("c = 5", font_size=30, color=ORANGE)
        
        math_box = VGroup(formula, step1, step2, step3, step4)
        math_box.arrange(DOWN, buff=0.4, aligned_edge=LEFT)
        math_box.shift(LEFT * 3 + DOWN * 0.5)
        
        # Animations
        self.play(Write(title))
        self.wait(0.5)
        
        self.play(Create(triangle), Create(right_angle), run_time=1.5)
        self.play(Write(label_a), Write(label_b))
        self.wait(0.5)
        
        self.play(Write(formula))
        self.wait(0.5)
        
        self.play(Indicate(label_a), Indicate(label_b))
        self.play(Write(step1))
        self.wait(0.5)
        
        self.play(Write(step2))
        self.wait(0.5)
        
        self.play(Write(step3))
        self.wait(0.5)
        
        self.play(Write(step4))
        self.play(Write(label_c))
        self.play(Indicate(label_c), Indicate(step4))
        self.wait(2)