#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    segvision_desktop_host_lib::run();
}
