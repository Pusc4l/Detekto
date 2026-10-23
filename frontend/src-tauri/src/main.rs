// Sembunyikan jendela konsol pada build rilis Windows.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    detekto_lib::run()
}
