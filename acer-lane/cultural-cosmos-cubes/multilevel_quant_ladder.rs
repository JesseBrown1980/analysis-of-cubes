// Exact multi-level quant ladder for the ACER cultural/cosmos cube lane.
//
// This is a representation/replay proof, not a physical quantum claim and not
// a compression claim. Each destination level receives:
//   exact transcode -> distinct SHA-seeded language -> quotient+residual quant.
// The residual makes the local quant exactly reversible. The complete backpath
// must restore the original source bytes and SHA-256.

use std::collections::HashSet;
use std::convert::TryInto;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

type R<T> = Result<T, String>;

#[derive(Clone, Copy)]
struct Level {
    name: &'static str,
    bits: u32,
    step: u16,
}

const LEVELS: [Level; 4] = [
    Level { name: "BEHCS64", bits: 6, step: 2 },
    Level { name: "BEHCS256", bits: 8, step: 4 },
    Level { name: "BEHCS1024", bits: 10, step: 8 },
    Level { name: "BEHCS4096", bits: 12, step: 16 },
];

const FAMILIES: [(&str, usize); 3] = [
    ("CUBE_8POLE", 8),
    ("TRI_12SECTOR", 12),
    ("PI_20LENS", 20),
];

fn sha256(data: &[u8]) -> [u8; 32] {
    const K: [u32; 64] = [
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
    ];
    let mut msg = data.to_vec();
    let bit_len = (msg.len() as u64).wrapping_mul(8);
    msg.push(0x80);
    while msg.len() % 64 != 56 { msg.push(0); }
    msg.extend_from_slice(&bit_len.to_be_bytes());
    let mut h = [
        0x6a09e667u32,0xbb67ae85,0x3c6ef372,0xa54ff53a,
        0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19
    ];
    for chunk in msg.chunks_exact(64) {
        let mut w = [0u32; 64];
        for i in 0..16 {
            w[i] = u32::from_be_bytes(chunk[i * 4..i * 4 + 4].try_into().unwrap());
        }
        for i in 16..64 {
            let s0 = w[i-15].rotate_right(7) ^ w[i-15].rotate_right(18) ^ (w[i-15] >> 3);
            let s1 = w[i-2].rotate_right(17) ^ w[i-2].rotate_right(19) ^ (w[i-2] >> 10);
            w[i] = w[i-16].wrapping_add(s0).wrapping_add(w[i-7]).wrapping_add(s1);
        }
        let (mut a,mut b,mut c,mut d,mut e,mut f,mut g,mut hh) =
            (h[0],h[1],h[2],h[3],h[4],h[5],h[6],h[7]);
        for i in 0..64 {
            let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let ch = (e & f) ^ ((!e) & g);
            let t1 = hh.wrapping_add(s1).wrapping_add(ch).wrapping_add(K[i]).wrapping_add(w[i]);
            let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let t2 = s0.wrapping_add(maj);
            hh=g; g=f; f=e; e=d.wrapping_add(t1); d=c; c=b; b=a; a=t1.wrapping_add(t2);
        }
        h[0]=h[0].wrapping_add(a); h[1]=h[1].wrapping_add(b);
        h[2]=h[2].wrapping_add(c); h[3]=h[3].wrapping_add(d);
        h[4]=h[4].wrapping_add(e); h[5]=h[5].wrapping_add(f);
        h[6]=h[6].wrapping_add(g); h[7]=h[7].wrapping_add(hh);
    }
    let mut out = [0u8; 32];
    for (i, value) in h.iter().enumerate() {
        out[i * 4..i * 4 + 4].copy_from_slice(&value.to_be_bytes());
    }
    out
}

fn hex(bytes: &[u8]) -> String {
    const H: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for &b in bytes {
        out.push(H[(b >> 4) as usize] as char);
        out.push(H[(b & 15) as usize] as char);
    }
    out
}

fn sha_hex(data: &[u8]) -> String { hex(&sha256(data)) }

fn symbols(bytes: &[u8], bits: u32) -> Vec<u16> {
    let mut out = Vec::new();
    let mut acc = 0u32;
    let mut held = 0u32;
    let mask = (1u32 << bits) - 1;
    for &b in bytes {
        acc = (acc << 8) | b as u32;
        held += 8;
        while held >= bits {
            held -= bits;
            out.push(((acc >> held) & mask) as u16);
        }
    }
    if held > 0 {
        out.push(((acc << (bits - held)) & mask) as u16);
    }
    out
}

fn bytes(syms: &[u16], bits: u32, original_len: usize) -> Vec<u8> {
    let mut out = Vec::with_capacity(original_len);
    let mut acc = 0u32;
    let mut held = 0u32;
    let mask = (1u32 << bits) - 1;
    for &sym in syms {
        acc = (acc << bits) | (sym as u32 & mask);
        held += bits;
        while held >= 8 {
            held -= 8;
            out.push(((acc >> held) & 0xff) as u8);
        }
    }
    out.truncate(original_len);
    out
}

fn pack(syms: &[u16], bits: u32) -> Vec<u8> {
    let mut out = Vec::new();
    let mut acc = 0u32;
    let mut held = 0u32;
    for &sym in syms {
        acc = (acc << bits) | sym as u32;
        held += bits;
        while held >= 8 {
            held -= 8;
            out.push(((acc >> held) & 0xff) as u8);
        }
    }
    if held > 0 { out.push(((acc << (8 - held)) & 0xff) as u8); }
    out
}

fn codebook(seed: &[u8; 32], bits: u32) -> (Vec<u16>, Vec<u16>, String) {
    let size = 1usize << bits;
    let mut keyed: Vec<([u8; 32], usize)> = (0..size).map(|value| {
        let mut input = b"MULTILEVEL-LANGUAGE-V1\0".to_vec();
        input.extend_from_slice(seed);
        input.extend_from_slice(&(value as u64).to_le_bytes());
        (sha256(&input), value)
    }).collect();
    keyed.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.cmp(&b.1)));
    let mut forward = vec![0u16; size];
    for (new, (_, old)) in keyed.into_iter().enumerate() { forward[old] = new as u16; }
    let mut inverse = vec![0u16; size];
    for (old, &new) in forward.iter().enumerate() { inverse[new as usize] = old as u16; }
    let mut raw = Vec::with_capacity(size * 2);
    for &value in &forward { raw.extend_from_slice(&value.to_le_bytes()); }
    (forward, inverse, sha_hex(&raw))
}

fn map_symbols(input: &[u16], map: &[u16]) -> Vec<u16> {
    input.iter().map(|&value| map[value as usize]).collect()
}

fn quantize(input: &[u16], step: u16) -> (Vec<u16>, Vec<u16>) {
    let buckets = input.iter().map(|&value| value / step).collect();
    let residuals = input.iter().map(|&value| value % step).collect();
    (buckets, residuals)
}

fn dequantize(buckets: &[u16], residuals: &[u16], step: u16) -> R<Vec<u16>> {
    if buckets.len() != residuals.len() { return Err("quant length mismatch".into()); }
    Ok(buckets.iter().zip(residuals).map(|(&q, &r)| q * step + r).collect())
}

fn load_source(dir: &Path) -> R<Vec<u8>> {
    let mut files = Vec::new();
    for entry in fs::read_dir(dir).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        if entry.file_type().map_err(|e| e.to_string())?.is_file() {
            let name = entry.file_name().to_string_lossy().to_string();
            if !name.ends_with(".sha256") { files.push(name); }
        }
    }
    files.sort();
    let mut out = Vec::new();
    for name in files { out.extend_from_slice(&fs::read(dir.join(name)).map_err(|e| e.to_string())?); }
    if out.is_empty() { return Err("empty source".into()); }
    Ok(out)
}

fn fold(domain: &str, parent: &str, leaves: &[String]) -> String {
    let mut sorted = leaves.to_vec();
    sorted.sort();
    let mut input = domain.as_bytes().to_vec();
    input.push(0);
    input.extend_from_slice(parent.as_bytes());
    for leaf in sorted {
        input.extend_from_slice(&(leaf.len() as u32).to_le_bytes());
        input.extend_from_slice(leaf.as_bytes());
    }
    sha_hex(&input)
}

fn write_lf(path: &Path, text: &str) -> R<()> {
    if let Some(parent) = path.parent() { fs::create_dir_all(parent).map_err(|e| e.to_string())?; }
    fs::write(path, text.replace("\r\n", "\n").replace('\r', "\n").as_bytes()).map_err(|e| e.to_string())
}

fn sidecar(path: &Path) -> R<String> {
    let hash = sha_hex(&fs::read(path).map_err(|e| e.to_string())?);
    let name = path.file_name().unwrap().to_string_lossy();
    write_lf(&PathBuf::from(format!("{}.sha256", path.display())), &format!("{}  {}\n", hash, name))?;
    Ok(hash)
}

fn run(source_dir: &Path, output_dir: &Path, seat: &str) -> R<()> {
    let source = load_source(source_dir)?;
    let source_sha = sha_hex(&source);
    let mut rows = vec![
        format!("MLHDR|schema=ASOLARIA-MULTILEVEL-QUANT-LADDER-V1|seat={}|source_bytes={}|source_sha256={}|levels=64,256,1024,4096|families=8,12,20|physical_quantum_claim=0|compression_claim=0|claims_final_apex=0|json=0", seat, source.len(), source_sha),
        "STACK|within_level=represent_then_language_then_residualized_quant|between_levels=decode_previous_then_encode_destination|backpath=4096_to_1024_to_256_to_64_to_bytes|json=0".into(),
    ];
    let mut family_roots = Vec::new();
    let mut all_codebooks = HashSet::new();
    let mut total_bodies = 0usize;
    let mut total_level_states = 0usize;

    for (family, count) in FAMILIES {
        let mut body_leaves = Vec::new();
        for body_index in 1..=count {
            let start = (body_index - 1) * source.len() / count;
            let end = body_index * source.len() / count;
            let body = &source[start..end];
            let body_sha = sha_hex(body);
            let mut previous_symbols: Option<(Vec<u16>, u32)> = None;
            let mut level_states: Vec<(Level, Vec<u16>, Vec<u16>, Vec<u16>, Vec<u16>)> = Vec::new();

            for level in LEVELS {
                let represented = if let Some((ref prior, prior_bits)) = previous_symbols {
                    let recovered = bytes(prior, prior_bits, body.len());
                    if recovered != body { return Err(format!("{} body {} translator source mismatch", family, body_index)); }
                    symbols(&recovered, level.bits)
                } else {
                    symbols(body, level.bits)
                };
                if bytes(&represented, level.bits, body.len()) != body {
                    return Err(format!("{} body {} {} representation restore", family, body_index, level.name));
                }

                let mut seed_input = b"MULTILEVEL-BODY-KEY-V1\0".to_vec();
                seed_input.extend_from_slice(source_sha.as_bytes());
                seed_input.extend_from_slice(family.as_bytes());
                seed_input.extend_from_slice(&(body_index as u64).to_le_bytes());
                seed_input.extend_from_slice(&level.bits.to_le_bytes());
                let seed = sha256(&seed_input);
                let (language, inverse, language_sha) = codebook(&seed, level.bits);
                if !all_codebooks.insert(language_sha.clone()) {
                    return Err(format!("duplicate language {}", language_sha));
                }
                let spoken = map_symbols(&represented, &language);
                let (buckets, residuals) = quantize(&spoken, level.step);
                let restored_spoken = dequantize(&buckets, &residuals, level.step)?;
                let heard = map_symbols(&restored_spoken, &inverse);
                if heard != represented || bytes(&heard, level.bits, body.len()) != body {
                    return Err(format!("{} body {} {} local quant restore", family, body_index, level.name));
                }

                rows.push(format!(
                    "LEVEL|family={}|body={:02}|level={}|bits={}|symbols={}|step={}|language_sha256={}|represented_sha256={}|bucket_sha256={}|residual_sha256={}|translator_exact=1|language_exact=1|quant_exact_with_residual=1|json=0",
                    family, body_index, level.name, level.bits, represented.len(), level.step,
                    language_sha, sha_hex(&pack(&represented, level.bits)),
                    sha_hex(&pack(&buckets, level.bits)), sha_hex(&pack(&residuals, level.bits))
                ));
                previous_symbols = Some((represented.clone(), level.bits));
                level_states.push((level, represented, spoken, buckets, residuals));
                total_level_states += 1;
            }

            let mut reverse_bytes = body.to_vec();
            for (level, represented, _spoken, buckets, residuals) in level_states.iter().rev() {
                let mut seed_input = b"MULTILEVEL-BODY-KEY-V1\0".to_vec();
                seed_input.extend_from_slice(source_sha.as_bytes());
                seed_input.extend_from_slice(family.as_bytes());
                seed_input.extend_from_slice(&(body_index as u64).to_le_bytes());
                seed_input.extend_from_slice(&level.bits.to_le_bytes());
                let seed = sha256(&seed_input);
                let (_language, inverse, _language_sha) = codebook(&seed, level.bits);
                let restored_spoken = dequantize(buckets, residuals, level.step)?;
                let restored_repr = map_symbols(&restored_spoken, &inverse);
                if &restored_repr != represented {
                    return Err(format!("{} body {} {} reverse state mismatch", family, body_index, level.name));
                }
                reverse_bytes = bytes(&restored_repr, level.bits, body.len());
                if reverse_bytes != body {
                    return Err(format!("{} body {} {} reverse byte mismatch", family, body_index, level.name));
                }
            }
            let body_leaf = fold("MULTILEVEL-BODY-V1", &body_sha, &rows.iter().rev().take(4).cloned().collect::<Vec<_>>());
            rows.push(format!("BODYRESTORE|family={}|body={:02}|source_sha256={}|backpath=4096,1024,256,64,bytes|restore=1|leaf_sha256={}|json=0", family, body_index, body_sha, body_leaf));
            body_leaves.push(body_leaf);
            total_bodies += 1;
        }
        let family_root = fold("MULTILEVEL-FAMILY-V1", &source_sha, &body_leaves);
        rows.push(format!("FAMILYROOT|family={}|bodies={}|levels=4|root={}|json=0", family, count, family_root));
        family_roots.push(family_root);
    }

    let omega = fold("MULTILEVEL-OMEGA-V1", &source_sha, &family_roots);
    rows.push(format!("MLOMEGA|families=3|bodies={}|level_states={}|distinct_languages={}|omega_unified={}|source_restore=1|compression_ratio=NOT_CLAIMED|physical_quantum_projection=UNVERIFIED|claims_final_apex=0|json=0", total_bodies, total_level_states, all_codebooks.len(), omega));
    rows.push(format!("MLFTR|status=PASS|source_sha256={}|omega_unified={}|json=0", source_sha, omega));

    let text = rows.join("\n") + "\n";
    let hbp = output_dir.join("MULTILEVEL-QUANT-RESULT.hbp");
    write_lf(&hbp, &text)?;
    let hbp_sha = sidecar(&hbp)?;
    let mut hbi_rows = Vec::new();
    for (index, row) in text.lines().enumerate() {
        hbi_rows.push(format!("HBI|row={}|sha256={}|json=0", index + 1, sha_hex(row.as_bytes())));
    }
    let hbi = output_dir.join("MULTILEVEL-QUANT-RESULT.hbi");
    write_lf(&hbi, &(hbi_rows.join("\n") + "\n"))?;
    let hbi_sha = sidecar(&hbi)?;
    let sums = output_dir.join("SHA256SUMS.multilevel");
    write_lf(&sums, &format!("{}  MULTILEVEL-QUANT-RESULT.hbp\n{}  MULTILEVEL-QUANT-RESULT.hbi\n", hbp_sha, hbi_sha))?;
    sidecar(&sums)?;
    println!("MULTILEVEL_QUANT_PASS|families=3|bodies={}|level_states={}|distinct_languages={}|omega_unified={}|source_sha256={}|json=0", total_bodies, total_level_states, all_codebooks.len(), omega, source_sha);
    Ok(())
}

fn selftest() -> R<()> {
    let data = b"64 -> 256 -> 1024 -> 4096 -> 1024 -> 256 -> 64";
    let mut prior: Option<(Vec<u16>, u32)> = None;
    for level in LEVELS {
        let represented = if let Some((ref syms, bits)) = prior {
            symbols(&bytes(syms, bits, data.len()), level.bits)
        } else {
            symbols(data, level.bits)
        };
        let seed = sha256(level.name.as_bytes());
        let (forward, inverse, _) = codebook(&seed, level.bits);
        let spoken = map_symbols(&represented, &forward);
        let (q, r) = quantize(&spoken, level.step);
        let restored = map_symbols(&dequantize(&q, &r, level.step)?, &inverse);
        if restored != represented || bytes(&restored, level.bits, data.len()) != data {
            return Err(format!("selftest failed at {}", level.name));
        }
        prior = Some((represented, level.bits));
    }
    println!("MULTILEVEL_SELFTEST_PASS|levels=64,256,1024,4096|exact=1|json=0");
    Ok(())
}

fn flag(args: &[String], name: &str) -> R<String> {
    let index = args.iter().position(|arg| arg == name).ok_or_else(|| format!("missing {}", name))?;
    args.get(index + 1).cloned().ok_or_else(|| format!("missing value {}", name))
}

fn main() -> Result<(), String> {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        return Err("usage: selftest | build --source DIR --output DIR [--seat ACER]".into());
    }
    match args[1].as_str() {
        "selftest" => selftest(),
        "build" => {
            let source = PathBuf::from(flag(&args, "--source")?);
            let output = PathBuf::from(flag(&args, "--output")?);
            let seat = flag(&args, "--seat").unwrap_or_else(|_| "ACER".into());
            run(&source, &output, &seat)
        }
        _ => Err("unknown command".into()),
    }
}
