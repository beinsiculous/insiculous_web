// @param speed: f32 = 300.0
// @param bound_x: f32 = 370.0
// @param bound_y: f32 = 270.0

// Kinematic movement runs in `early_update`, before the physics step, so the
// body's target for this frame is set by the time the step consumes it.
fn early_update(me, view, params, cmd, dt) {
    let x = me.position.x + view.move_x(0) * params.speed * dt;
    let y = me.position.y + view.move_y(0) * params.speed * dt;

    // The walls are solid to a dynamic body, but a kinematic one drives
    // straight through them: the clamp is what keeps the Player on screen.
    x = max(min(x, params.bound_x), -params.bound_x);
    y = max(min(y, params.bound_y), -params.bound_y);

    cmd.set_kinematic_target(me, vec2(x, y));
}
