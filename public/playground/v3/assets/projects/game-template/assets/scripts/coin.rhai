// Collisions are `update`-only: the view carries the contacts the physics
// step drained this frame, and `early_update` runs before that step.
fn update(me, view, params, cmd, dt) {
    if view.has_collision_started(me, "Player") {
        let banked = view.blackboard_int("coins", 0) + 1;
        cmd.set_blackboard_int("coins", banked);

        // Hop to the next of four fixed corners. The corners are a list, not a
        // parameter: a count the inspector could set to zero would divide by it.
        // `reset_body` is the documented move for a body — a bare
        // `set_position` leaves the physics body behind.
        let corners = [vec2(200.0, 150.0), vec2(-200.0, 150.0), vec2(-200.0, -150.0), vec2(200.0, -150.0)];
        cmd.reset_body(me, corners[banked % 4]);
    }
}
