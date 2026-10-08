//! Native Rust control for the C++/Crubit fixed-pair benchmark.
use locale_collator::Collator;
use std::{env, hint::black_box, io::{self, Read}, time::Instant};

fn run(collator: &Collator, pairs: &[(&[u8], &[u8])], iterations: u32) -> u64 {
    let mut hash = 14695981039346656037u64;
    for _ in 0..iterations {
        // Keep the optimizer from precomputing repeated comparisons.
        for &(left, right) in black_box(pairs) {
            let result = collator.compare_utf8(left, right);
            hash = (hash ^ (result + 1) as u64).wrapping_mul(1099511628211);
        }
    }
    black_box(hash)
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = env::args().skip(1);
    let locale = args.next().ok_or("expected BCP 47 locale")?;
    let iterations: u32 = args.next().ok_or("expected iteration count")?.parse()?;
    if iterations == 0 || args.next().is_some() {
        return Err("expected locale and positive iteration count".into());
    }
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let lines: Vec<_> = input.split_terminator('\n').collect();
    if lines.is_empty() || lines.len() % 2 != 0 {
        return Err("expected a nonempty, even number of lines".into());
    }
    let pairs: Vec<_> = lines.chunks_exact(2)
        .map(|pair| (pair[0].as_bytes(), pair[1].as_bytes())).collect();
    let setup_start = Instant::now();
    let collator = Collator::new(locale.as_bytes())
        .map_err(|code| format!("collator error {code}"))?;
    let setup_ns = setup_start.elapsed().as_nanos();
    let warmup = run(&collator, &pairs, 1);
    let start = Instant::now();
    let checksum = run(&collator, &pairs, iterations);
    let compare_ns = start.elapsed().as_nanos();
    println!("{{\"iterations\":{iterations},\"pairs\":{},\"setup_ns\":{setup_ns},\"compare_ns\":{compare_ns},\"warmup_checksum\":{warmup},\"checksum\":{checksum}}}", pairs.len());
    Ok(())
}
