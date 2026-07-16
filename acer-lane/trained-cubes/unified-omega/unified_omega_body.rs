// Unified Omega construct — three geometry families from ONE shared 0-loss reversible root.
// Per the 43-agent design: CUBE(8 poles,800 cells) inside E12-SEAM(12 sectors,1200) inside
// PI20-HULL(20 lenses,2000). All three cut from ONE shared source (the shared root key), each
// body its own SHA-seeded 1024-glyph language (never English), every cell byte-exact reversible
// (state_match=1). Two-level OmniSubmit fold: per-family sub-omega, then
// Omega_unified = H(D || e || parent || sorted[omega_8, omega_12, omega_pi]).
// MEASURED: reversible training + language distinctness + omega fold. HELD: N->inf, floors 3+,
// engine promotion, apex formation, claims_final_apex=0 (human-apex reserved). No physics claims.

use std::collections::{HashMap, HashSet};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

type R<T> = Result<T, String>;
const BITS: u32 = 10;
const A_NAMES: [&str; 8] = ["G_ID","G_REV","G_XORD","G_ROT","G_HALF","G_BLKREV","G_EVODD","G_QPRISM"];

// ---------- sha256 ----------
fn sha256(data: &[u8]) -> [u8; 32] {
    const K: [u32; 64] = [
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
    let mut msg = data.to_vec();
    let bl = (msg.len() as u64).wrapping_mul(8);
    msg.push(0x80);
    while msg.len() % 64 != 56 { msg.push(0); }
    msg.extend_from_slice(&bl.to_be_bytes());
    let mut h: [u32;8]=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
    for ch in msg.chunks_exact(64) {
        let mut w=[0u32;64];
        for i in 0..16 { w[i]=u32::from_be_bytes(ch[i*4..i*4+4].try_into().unwrap()); }
        for i in 16..64 {
            let s0=w[i-15].rotate_right(7)^w[i-15].rotate_right(18)^(w[i-15]>>3);
            let s1=w[i-2].rotate_right(17)^w[i-2].rotate_right(19)^(w[i-2]>>10);
            w[i]=w[i-16].wrapping_add(s0).wrapping_add(w[i-7]).wrapping_add(s1);
        }
        let (mut a,mut b,mut c,mut d,mut e,mut f,mut g,mut hh)=(h[0],h[1],h[2],h[3],h[4],h[5],h[6],h[7]);
        for i in 0..64 {
            let s1=e.rotate_right(6)^e.rotate_right(11)^e.rotate_right(25);
            let cbh=(e&f)^((!e)&g);
            let t1=hh.wrapping_add(s1).wrapping_add(cbh).wrapping_add(K[i]).wrapping_add(w[i]);
            let s0=a.rotate_right(2)^a.rotate_right(13)^a.rotate_right(22);
            let maj=(a&b)^(a&c)^(b&c);
            let t2=s0.wrapping_add(maj);
            hh=g;g=f;f=e;e=d.wrapping_add(t1);d=c;c=b;b=a;a=t1.wrapping_add(t2);
        }
        h[0]=h[0].wrapping_add(a);h[1]=h[1].wrapping_add(b);h[2]=h[2].wrapping_add(c);h[3]=h[3].wrapping_add(d);
        h[4]=h[4].wrapping_add(e);h[5]=h[5].wrapping_add(f);h[6]=h[6].wrapping_add(g);h[7]=h[7].wrapping_add(hh);
    }
    let mut o=[0u8;32];
    for (i,v) in h.iter().enumerate(){o[i*4..i*4+4].copy_from_slice(&v.to_be_bytes());}
    o
}
fn hex(b:&[u8])->String{const H:&[u8;16]=b"0123456789abcdef";let mut s=String::with_capacity(b.len()*2);for &x in b{s.push(H[(x>>4)as usize]as char);s.push(H[(x&15)as usize]as char);}s}
fn sha_hex(d:&[u8])->String{hex(&sha256(d))}
fn write_lf(p:&Path,t:&str)->R<()>{if let Some(par)=p.parent(){fs::create_dir_all(par).map_err(|e|e.to_string())?;}fs::write(p,t.replace("\r\n","\n").replace('\r',"\n").as_bytes()).map_err(|e|e.to_string())}
fn write_sidecar(p:&Path)->R<String>{let b=fs::read(p).map_err(|e|e.to_string())?;let d=sha_hex(&b);let n=p.file_name().unwrap().to_string_lossy();write_lf(&PathBuf::from(format!("{}.sha256",p.display())),&format!("{}  {}\n",d,n))?;Ok(d)}
fn pid16(l:&str)->String{sha_hex(l.as_bytes())[..16].to_string()}

// ---------- LZ1 ----------
fn flush(o:&mut Vec<u8>,l:&mut Vec<u8>){let mut a=0;while a<l.len(){let n=(l.len()-a).min(u16::MAX as usize);o.push(0);o.extend_from_slice(&(n as u16).to_le_bytes());o.extend_from_slice(&l[a..a+n]);a+=n;}l.clear();}
fn lz_c(d:&[u8])->Vec<u8>{let mut o=b"LZ1\0".to_vec();o.extend_from_slice(&(d.len()as u64).to_le_bytes());let mut last:HashMap<u32,usize>=HashMap::new();let mut lit=Vec::new();let mut i=0;while i<d.len(){let k=if i+2<d.len(){Some(((d[i]as u32)<<16)|((d[i+1]as u32)<<8)|d[i+2]as u32)}else{None};let mut best=0;let mut off=0;if let Some(kk)=k{if let Some(&p)=last.get(&kk){let o2=i-p;if o2>0&&o2<=u16::MAX as usize{let mx=(d.len()-i).min(u16::MAX as usize);while best<mx&&d[p+best]==d[i+best]{best+=1;}if best>=4{off=o2;}}}}if best>=4{flush(&mut o,&mut lit);o.push(1);o.extend_from_slice(&(off as u16).to_le_bytes());o.extend_from_slice(&(best as u16).to_le_bytes());for pos in i..i+best{if pos+2<d.len(){let kk=((d[pos]as u32)<<16)|((d[pos+1]as u32)<<8)|d[pos+2]as u32;last.insert(kk,pos);}}i+=best;}else{if let Some(kk)=k{last.insert(kk,i);}lit.push(d[i]);i+=1;if lit.len()==u16::MAX as usize{flush(&mut o,&mut lit);}}}flush(&mut o,&mut lit);o}
fn lz_d(d:&[u8])->R<Vec<u8>>{if d.len()<12||&d[..4]!=b"LZ1\0"{return Err("lz hdr".into());}let want=u64::from_le_bytes(d[4..12].try_into().unwrap())as usize;let mut a=12;let mut o=Vec::with_capacity(want);while a<d.len()&&o.len()<want{let t=d[a];a+=1;if t==0{if a+2>d.len(){return Err("lit".into());}let n=u16::from_le_bytes(d[a..a+2].try_into().unwrap())as usize;a+=2;if a+n>d.len(){return Err("lit ov".into());}o.extend_from_slice(&d[a..a+n]);a+=n;}else if t==1{if a+4>d.len(){return Err("m".into());}let of=u16::from_le_bytes(d[a..a+2].try_into().unwrap())as usize;let n=u16::from_le_bytes(d[a+2..a+4].try_into().unwrap())as usize;a+=4;if of==0||of>o.len(){return Err("moff".into());}for _ in 0..n{let b=o[o.len()-of];o.push(b);}}else{return Err("tag".into());}}if o.len()!=want{return Err("len".into());}Ok(o)}

// ---------- predictor (bits + runtime epochs) ----------
#[derive(Clone,PartialEq,Eq)] struct BS{total:u32,bsym:u16,bcnt:u32}
#[derive(Clone,PartialEq,Eq)] struct PM{bits:u32,order:u8,dir:u8,counts:HashMap<(u64,u16),u32>,best:HashMap<u64,BS>,commit:[u8;32],ep:u32}
impl PM{
    fn new(bits:u32,order:u8,dir:u8)->Self{let mut dm=b"PAIS-PREDICTOR-STATE-V2|".to_vec();dm.push(bits as u8);dm.push(order);dm.push(dir);Self{bits,order,dir,counts:HashMap::new(),best:HashMap::new(),commit:sha256(&dm),ep:0}}
    fn mask(&self)->u64{(1u64<<(self.order as u32*self.bits))-1}
    fn key(&self,ctx:u64,seen:usize)->u64{let n=seen.min(self.order as usize)as u64;ctx|(n<<50)|((self.order as u64)<<56)}
    fn pred(&self,k:u64)->(u16,u32,u32){self.best.get(&k).map(|s|(s.bsym,s.bcnt,s.total)).unwrap_or((0,0,0))}
    fn upd(&mut self,k:u64,sym:u16){let c=self.counts.entry((k,sym)).or_insert(0);*c+=1;let nc=*c;let s=self.best.entry(k).or_insert(BS{total:0,bsym:0,bcnt:0});s.total=s.total.saturating_add(1);if nc>s.bcnt||(nc==s.bcnt&&sym<s.bsym){s.bsym=sym;s.bcnt=nc;}}
    fn fin(&mut self,seq:&[u16]){let pk=pack(seq,self.bits);let mut b=Vec::new();b.extend_from_slice(&self.commit);b.extend_from_slice(&sha256(&pk));b.extend_from_slice(&(self.ep+1).to_le_bytes());b.extend_from_slice(&(self.counts.len()as u64).to_le_bytes());self.commit=sha256(&b);self.ep+=1;}
    fn enc(&mut self,seq:&[u16])->Vec<u16>{let mut r=Vec::with_capacity(seq.len());let mut ctx=0u64;let mut seen=0;let m=self.mask();for &sym in seq{let k=self.key(ctx,seen);let(p,_,_)=self.pred(k);r.push(sym^p);self.upd(k,sym);ctx=((ctx<<self.bits)|(sym as u64))&m;seen+=1;}self.fin(seq);r}
    fn dec(&mut self,res:&[u16])->Vec<u16>{let mut seq=Vec::with_capacity(res.len());let mut ctx=0u64;let mut seen=0;let m=self.mask();for &rr in res{let k=self.key(ctx,seen);let(p,_,_)=self.pred(k);let sym=rr^p;self.upd(k,sym);seq.push(sym);ctx=((ctx<<self.bits)|(sym as u64))&m;seen+=1;}self.fin(&seq);seq}
}

// ---------- glyphs ----------
fn b2g(b:&[u8],bits:u32)->Vec<u16>{let cnt=(b.len()*8+bits as usize-1)/bits as usize;let mut o=Vec::with_capacity(cnt);let mut a=0u32;let mut nb=0u32;for &x in b{a=(a<<8)|(x as u32);nb+=8;while nb>=bits{nb-=bits;o.push(((a>>nb)&((1<<bits)-1))as u16);}}if nb>0{o.push(((a<<(bits-nb))&((1<<bits)-1))as u16);}o}
fn g2b(g:&[u16],bits:u32,nl:usize)->Vec<u8>{let mut o=Vec::with_capacity(nl+2);let mut a=0u32;let mut nb=0u32;for &x in g{a=(a<<bits)|(x as u32);nb+=bits;while nb>=8{nb-=8;o.push(((a>>nb)&0xff)as u8);}}if nb>0{o.push(((a<<(8-nb))&0xff)as u8);}o.truncate(nl);o}
fn pack(g:&[u16],bits:u32)->Vec<u8>{let mut o=Vec::new();let mut a=0u32;let mut nb=0u32;for &x in g{a=(a<<bits)|(x as u32);nb+=bits;while nb>=8{nb-=8;o.push(((a>>nb)&0xff)as u8);}}if nb>0{o.push(((a<<(8-nb))&0xff)as u8);}o}
fn unpack(b:&[u8],bits:u32,cnt:usize)->Vec<u16>{let mut o=Vec::with_capacity(cnt);let mut a=0u32;let mut nb=0u32;for &x in b{a=(a<<8)|(x as u32);nb+=8;while nb>=bits{if o.len()==cnt{break;}nb-=bits;o.push(((a>>nb)&((1<<bits)-1))as u16);}if o.len()==cnt{break;}}o}
fn revb(v:u16,n:u32)->u16{let mut o=0;for i in 0..n{if v&(1<<i)!=0{o|=1<<(n-1-i);}}o}
fn g_r(d:&[u16])->Vec<u16>{d.iter().rev().copied().collect()}
fn g_n(d:&[u16],bits:u32)->Vec<u16>{let h=bits/2;let hm=(1u16<<h)-1;d.iter().map(|&g|((g&hm)<<h)|(g>>h)).collect()}
fn g_q(d:&[u16],bits:u32)->Vec<u16>{let h=bits/2;let hm=(1u16<<h)-1;d.iter().map(|&g|(revb(g>>h,h)<<h)|revb(g&hm,h)).collect()}
fn gview(d:&[u16],m:u8,bits:u32)->Vec<u16>{let mut o=d.to_vec();if m&1!=0{o=g_r(&o);}if m&2!=0{o=g_n(&o,bits);}if m&4!=0{o=g_q(&o,bits);}o}
fn group_gate(d:&[u16],bits:u32)->(bool,String){let rr=g_r(&g_r(d))==*d;let nn=g_n(&g_n(d,bits),bits)==*d;let qq=g_q(&g_q(d,bits),bits)==*d;let rn=g_r(&g_n(d,bits))==g_n(&g_r(d),bits);let rq=g_r(&g_q(d,bits))==g_q(&g_r(d),bits);let nq=g_n(&g_q(d,bits),bits)==g_q(&g_n(d,bits),bits);let mut u=HashSet::new();for m in 0..8{u.insert(sha_hex(&pack(&gview(d,m,bits),bits)));}let rnq=gview(d,7,bits);let tot:Vec<u16>=d.iter().rev().map(|&g|revb(g,bits)).collect();let ok=rr&&nn&&qq&&rn&&rq&&nq&&u.len()==8&&rnq==tot;(ok,format!("sq={},{},{}|comm={},{},{}|distinct={}|rnq={}",u8::from(rr),u8::from(nn),u8::from(qq),u8::from(rn),u8::from(rq),u8::from(nq),u.len(),u8::from(rnq==tot)))}
fn xd(d:&[u16])->Vec<u16>{if d.is_empty(){return vec![];}let mut o=vec![d[0]];for i in 1..d.len(){o.push(d[i]^d[i-1]);}o}
fn xu(d:&[u16])->Vec<u16>{if d.is_empty(){return vec![];}let mut o=vec![d[0]];for i in 1..d.len(){let b=d[i]^o[i-1];o.push(b);}o}
fn rol(g:u16,bits:u32)->u16{let m=(1u16<<bits)-1;((g<<1)|(g>>(bits-1)))&m}
fn ror(g:u16,bits:u32)->u16{let m=(1u16<<bits)-1;((g>>1)|((g&1)<<(bits-1)))&m}
fn blkrev(d:&[u16],bl:usize)->Vec<u16>{let mut o=Vec::new();for c in d.chunks(bl){o.extend(c.iter().rev());}o}
fn evo(d:&[u16])->Vec<u16>{d.iter().step_by(2).chain(d.iter().skip(1).step_by(2)).copied().collect()}
fn uevo(d:&[u16])->Vec<u16>{let e=(d.len()+1)/2;let mut o=vec![0u16;d.len()];for i in 0..e{o[i*2]=d[i];}for i in e..d.len(){o[(i-e)*2+1]=d[i];}o}
fn qpo(nb:usize,ss:&[u8;32])->Vec<usize>{let mut k:Vec<([u8;32],usize)>=(0..nb).map(|i|{let mut s=b"QPRISM_GLYPH_V3|257|".to_vec();s.extend_from_slice(ss);s.extend_from_slice(&(i as u64).to_le_bytes());(sha256(&s),i)}).collect();k.sort_by(|a,b|a.0.cmp(&b.0).then(a.1.cmp(&b.1)));k.into_iter().map(|x|x.1).collect()}
fn qp(d:&[u16],ss:&[u8;32])->Vec<u16>{let bl=257;let n=d.len()/bl;let o=qpo(n,ss);let mut r=Vec::new();for i in o{r.extend_from_slice(&d[i*bl..(i+1)*bl]);}r.extend_from_slice(&d[n*bl..]);r}
fn uqp(d:&[u16],ss:&[u8;32])->Vec<u16>{let bl=257;let n=d.len()/bl;let o=qpo(n,ss);let mut r=vec![0u16;d.len()];for (p,i) in o.into_iter().enumerate(){r[i*bl..(i+1)*bl].copy_from_slice(&d[p*bl..(p+1)*bl]);}r[n*bl..].copy_from_slice(&d[n*bl..]);r}
fn a_ap(ix:usize,d:&[u16],bits:u32,ss:&[u8;32])->Vec<u16>{match ix{0=>d.to_vec(),1=>g_r(d),2=>xd(d),3=>d.iter().rev().map(|&g|rol(g,bits)).collect(),4=>g_n(d,bits),5=>blkrev(d,256),6=>evo(d),7=>qp(d,ss),_=>unreachable!()}}
fn a_in(ix:usize,d:&[u16],bits:u32,ss:&[u8;32])->Vec<u16>{match ix{0=>d.to_vec(),1=>g_r(d),2=>xu(d),3=>d.iter().map(|&g|ror(g,bits)).rev().collect(),4=>g_n(d,bits),5=>blkrev(d,256),6=>uevo(d),7=>uqp(d,ss),_=>unreachable!()}}

// ---------- language + omnisubmit ----------
fn codebook(bsha:&[u8;32],bits:u32)->(Vec<u16>,Vec<u16>,String){let n=1usize<<bits;let mut k:Vec<([u8;32],usize)>=(0..n).map(|g|{let mut s=b"LANGUAGE_GENESIS_V1|".to_vec();s.extend_from_slice(bsha);s.extend_from_slice(&(g as u64).to_le_bytes());(sha256(&s),g)}).collect();k.sort_by(|a,b|a.0.cmp(&b.0).then(a.1.cmp(&b.1)));let mut p=vec![0u16;n];for (nw,(_,od)) in k.into_iter().enumerate(){p[od]=nw as u16;}let mut inv=vec![0u16;n];for (od,&nw) in p.iter().enumerate(){inv[nw as usize]=od as u16;}let mut pb=Vec::with_capacity(n*2);for &x in &p{pb.extend_from_slice(&x.to_le_bytes());}(p,inv,sha_hex(&pb))}
fn speak(g:&[u16],p:&[u16])->Vec<u16>{g.iter().map(|&x|p[x as usize]).collect()}
fn cenc(f:&[(&str,&str)])->Vec<u8>{let mut o=Vec::new();for (k,v) in f{o.extend_from_slice(&(k.len()as u32).to_le_bytes());o.extend_from_slice(k.as_bytes());o.extend_from_slice(&(v.len()as u32).to_le_bytes());o.extend_from_slice(v.as_bytes());}o}
fn leaf(f:&[(&str,&str)])->String{let mut m=b"UNIFIED-LEAF-V1\0".to_vec();m.extend_from_slice(&cenc(f));sha_hex(&m)}
fn epoch_root(e:u64,parent:&str,leaves:&[String])->String{let mut s=leaves.to_vec();s.sort();let mut m=b"UNIFIED-OMEGA-V1\0".to_vec();m.extend_from_slice(&e.to_le_bytes());m.extend_from_slice(&(parent.len()as u32).to_le_bytes());m.extend_from_slice(parent.as_bytes());for l in &s{m.extend_from_slice(&(l.len()as u32).to_le_bytes());m.extend_from_slice(l.as_bytes());}sha_hex(&m)}

// ---------- shared source ----------
fn load_source(dir:&Path)->R<(Vec<u8>,String)>{let mut names=Vec::new();for e in fs::read_dir(dir).map_err(|x|x.to_string())?{let e=e.map_err(|x|x.to_string())?;let n=e.file_name().to_string_lossy().to_string();if n.ends_with(".sha256"){continue;}names.push(n);}names.sort();let mut d=Vec::new();for n in &names{d.extend_from_slice(&fs::read(dir.join(n)).map_err(|x|x.to_string())?);}let s=sha_hex(&d);Ok((d,s))}

struct BodyOut{index:usize,leaf:String,codebook:String,lambda:String,accepted:u64,held:u64,gain:u64}

fn train_body(fam:&str,index:usize,bytes:&[u8],epochs:usize,rows:&mut Vec<String>,seat:&str,shared_root:&str)->R<BodyOut>{
    let src=sha256(bytes);
    let raw=b2g(bytes,BITS);
    // language seeded by the SHARED ROOT + family + index (domain-separated child of one key)
    let mut kseed=b"KROOT|".to_vec();kseed.extend_from_slice(shared_root.as_bytes());kseed.push(b'|');kseed.extend_from_slice(fam.as_bytes());kseed.extend_from_slice(&(index as u64).to_le_bytes());
    let kbody=sha256(&kseed);
    let (perm,inv,cb)=codebook(&kbody,BITS);
    let g=speak(&raw,&perm);
    let heard:Vec<u16>=g.iter().map(|&x|inv[x as usize]).collect();
    if heard!=raw||g2b(&heard,BITS,bytes.len())!=bytes{return Err(format!("{} body {} language roundtrip",fam,index));}
    let nsha=sha256(&pack(&g,BITS));
    let (ok,gd)=group_gate(&g,BITS);
    if !ok{return Err(format!("{} body {} group gate {}",fam,index,gd));}
    rows.push(format!("BODYHDR|family={}|body={:02}|bits=10|bytes={}|glyphs={}|src_sha256={}|codebook_sha256={}|cells={}|json=0",fam,index,bytes.len(),g.len(),sha_hex(bytes),cb,8*10*epochs));
    rows.push(format!("LANGUAGE|family={}|body={:02}|law=LANGUAGE_GENESIS_V1|codebook_sha256={}|never_english=1|seeded_by=shared_root|json=0",fam,index,cb));
    rows.push(format!("GROUPGATE|family={}|body={:02}|{}|status=PASS|json=0",fam,index,gd));
    let mut gain=0u64;let mut acc=0u64;let mut held=0u64;
    for a in 0..8{
        let v=a_ap(a,&g,BITS,&nsha);
        if a_in(a,&v,BITS,&nsha)!=g{return Err(format!("{} body {} A{} inverse",fam,index,a));}
        let vp=pack(&v,BITS);
        for dir in 0..2u8{ for order in 1..=5u8{
            let seq:Vec<u16>=if dir==0{v.clone()}else{v.iter().rev().copied().collect()};
            let mut enc=PM::new(BITS,order,dir);let mut dec=PM::new(BITS,order,dir);
            for _e in 1..=epochs{
                let res=enc.enc(&seq);
                let pl=lz_c(&pack(&res,BITS));
                let dr=unpack(&lz_d(&pl)?,BITS,seq.len());
                let ds=dec.dec(&dr);
                if ds!=seq||enc.commit!=dec.commit{return Err(format!("{} body {} cell restore a={} d={} o={}",fam,index,a,dir,order));}
                let cost=pl.len();
                let gg=vp.len().saturating_sub(cost) as u64;
                if gg>0{acc+=1;gain+=gg;}else{held+=1;}
            }
        }}
        rows.push(format!("AVIEW|family={}|body={:02}|a={}|view_sha256={}|roundtrip=1|json=0",fam,index,A_NAMES[a],sha_hex(&vp)));
    }
    let total_cells=(8*10*epochs) as u64;
    if acc+held!=total_cells{return Err(format!("{} body {} cell count {} != {}",fam,index,acc+held,total_cells));}
    rows.push(format!("DENSITY|family={}|body={:02}|ledger=SHARED_ROOT_GLYPHS|gain_bytes={}|glyphs={}|accepted={}|held={}|meaning=structure_repetition_only|archive_ratio=NOT_CLAIMED|json=0",fam,index,gain,g.len(),acc,held));
    rows.push(format!("BODYRESTORE|family={}|body={:02}|src_sha256={}|restore=1|leaf_preimage=timing_free|json=0",fam,index,sha_hex(bytes)));
    let leaf_sha={let mut s=String::new();for r in rows.iter(){s.push_str(r);s.push('\n');}sha_hex(s.as_bytes())};
    rows.push(format!("OMEGALEAF|family={}|body={:02}|cells={}|leaf_sha256={}|restore=1|json=0",fam,index,total_cells,leaf_sha));
    let bpid=pid16(&format!("UNI-BODY|{}|{}",fam,sha_hex(bytes)));
    let cells_s=format!("{}",total_cells);
    let fields:[(&str,&str);10]=[("actor",seat),("verb","TRAIN"),("family",fam),("pid",&bpid),("cells",&cells_s),("codebook",&cb),("audit",&leaf_sha),("quorum","SEAT_SINGLE"),("omega_state","closure"),("claims_final_apex","0")];
    let lam=leaf(&fields);
    rows.push(format!("OMNISUBMIT|family={}|body={:02}|pid={}|lambda={}|wall_clock_in_leaf=0|claims_final_apex=0|json=0",fam,index,bpid,lam));
    Ok(BodyOut{index,leaf:leaf_sha,codebook:cb,lambda:lam,accepted:acc,held,gain})
}

fn train_family(fam:&str,n:usize,epochs:usize,src:&[u8],src_sha:&str,rows:&mut Vec<String>,seat:&str)->R<(String,String,u64,u64,u64)>{
    let ln=src.len();
    let mut leaves=Vec::new();let mut lambdas=Vec::new();
    let mut ta=0u64;let mut th=0u64;let mut tg=0u64;
    let mut seen_cb=HashSet::new();
    rows.push(format!("FAMILYHDR|family={}|bodies={}|epochs={}|cells_per_body={}|shared_root={}|json=0",fam,n,epochs,8*10*epochs,src_sha));
    for i in 1..=n{
        let start=(i-1)*ln/n;let end=i*ln/n;
        let bytes=&src[start..end];
        let bo=train_body(fam,i,bytes,epochs,rows,seat,src_sha)?;
        if !seen_cb.insert(bo.codebook.clone()){return Err(format!("{} duplicate codebook body {}",fam,i));}
        ta+=bo.accepted;th+=bo.held;tg+=bo.gain;
        leaves.push(format!("OMEGALEAFREF|family={}|body={:02}|leaf_sha256={}|codebook_sha256={}|lambda={}|json=0",fam,bo.index,bo.leaf,bo.codebook,bo.lambda));
        lambdas.push(bo.lambda.clone());
        println!("BODY_OK|family={}|body={:02}|cells={}|accepted={}|held={}|gain={}",fam,i,8*10*epochs,bo.accepted,bo.held,bo.gain);
    }
    let anchor=format!("OMEGAANCHOR|family={}|bodies={}|shared_root={}|epoch=1|json=0",fam,n,src_sha);
    let fam_omega={let mut s=anchor.clone();s.push('\n');for l in &leaves{s.push_str(l);s.push('\n');}sha_hex(s.as_bytes())};
    let fam_epoch_root=epoch_root(1,src_sha,&lambdas);
    rows.push(anchor);for l in leaves{rows.push(l);}
    rows.push(format!("FAMILYOMEGA|family={}|bodies={}|omega_sha256={}|epoch_root={}|accepted={}|held={}|gain_bytes={}|json=0",fam,n,fam_omega,fam_epoch_root,ta,th,tg));
    println!("FAMILY_OK|family={}|bodies={}|omega={}|epoch_root={}|accepted={}|held={}|gain={}",fam,n,fam_omega,fam_epoch_root,ta,th,tg);
    Ok((fam_omega,fam_epoch_root,ta,th,tg))
}

fn hbi_for(hbp:&str)->String{let mut o=String::new();for (i,l) in hbp.lines().enumerate(){o.push_str(&format!("HBI|row={}|sha256={}|hex={}|json=0\n",i+1,sha_hex(l.as_bytes()),hex(l.as_bytes())));}o}

fn run(src_dir:&Path,out:&Path,seat:&str)->R<()>{
    fs::create_dir_all(out).map_err(|e|e.to_string())?;
    let (src,src_sha)=load_source(src_dir)?;
    println!("SHARED_ROOT|source_bytes={}|sha256={}",src.len(),src_sha);
    // negative controls
    let zero=vec![0u16;4096];let (zp,_)=group_gate(&zero,BITS);if zp{return Err("zero distinctness control".into());}
    let mut rows=Vec::new();
    rows.push(format!("UNIFIEDHDR|schema=ASOLARIA-UNIFIED-OMEGA-8-12-PI-V1|authority=OPERATOR_BUILD_2026-07-16|mode=SHADOW_MEASURED|families=3|shared_root_sha256={}|cube=8x800|seam=12x1200|hull=20x2000|higher_floors=HELD|claims_final_apex=0|json=0",src_sha));
    rows.push(format!("SHAREDKEY|law=one_reversible_codec_root|k_body=H(root||family||index)|all_bodies_distinct_languages|restore=byte_exact_state_match|not_quantum_entanglement=1|json=0"));
    // three families from the ONE shared root
    let (o8,e8,a8,h8,g8)=train_family("CUBE_8POLE",8,10,&src,&src_sha,&mut rows,seat)?;   // 800 cells
    let (o12,e12,a12,h12,g12)=train_family("TRI_12SECTOR",12,15,&src,&src_sha,&mut rows,seat)?; // 1200
    let (o20,ep,a20,h20,g20)=train_family("PI_20LENS",20,25,&src,&src_sha,&mut rows,seat)?;   // 2000
    let _=(e8,e12,ep);
    // LEVEL 2: unified fold over the three family sub-omegas
    let unified=epoch_root(1,&src_sha,&vec![o8.clone(),o12.clone(),o20.clone()]);
    let ta=a8+a12+a20;let th=h8+h12+h20;let tg=g8+g12+g20;let cells=8*800+12*1200+20*2000;
    rows.push(format!("SUBOMEGAS|omega_8={}|omega_12={}|omega_pi={}|json=0",o8,o12,o20));
    rows.push(format!("UNIFIEDOMEGA|method=H(D||e||shared_root||sorted[omega_8,omega_12,omega_pi])|omega_unified={}|families=3|bodies=40|cells={}|accepted={}|held={}|gain_bytes={}|json=0",unified,cells,ta,th,tg));
    rows.push(format!("HELD|n_infinity=uncomputable|floors_3plus=operator_gated|engine_9check=DESIGN|apex_6of6=DESIGN|omega_gnn=SPEC_ONLY|owning_gate=UNVERIFIED|claims_final_apex=0_human_reserved|no_physics_claims=1|json=0"));
    rows.push(format!("UNIFIEDFTR|families=3|bodies=40|cells={}|accepted={}|held={}|omega_unified={}|status=PASS|json=0",cells,ta,th,unified));
    let text={let mut s=String::new();for r in &rows{s.push_str(r);s.push('\n');}s};
    let hp=out.join("UNIFIED-OMEGA-RESULT.hbp");write_lf(&hp,&text)?;let hps=write_sidecar(&hp)?;
    let hi=out.join("UNIFIED-OMEGA-RESULT.hbi");write_lf(&hi,&hbi_for(&text))?;let his=write_sidecar(&hi)?;
    let sums=format!("{}  UNIFIED-OMEGA-RESULT.hbp\n{}  UNIFIED-OMEGA-RESULT.hbi\n",hps,his);
    let sp=out.join("SHA256SUMS");write_lf(&sp,&sums)?;write_sidecar(&sp)?;
    println!("UNIFIED_OMEGA_PASS|families=3|bodies=40|cells={}|accepted={}|held={}|gain_bytes={}|omega_8={}|omega_12={}|omega_pi={}|omega_unified={}|result_sha256={}|claims_final_apex=0|higher_floors=HELD",cells,ta,th,tg,o8,o12,o20,unified,hps);
    Ok(())
}

fn selftest()->R<()>{
    let mut d=Vec::new();let mut s=sha256(b"UNIFIED-SELFTEST");while d.len()<40000{d.extend_from_slice(&s);s=sha256(&s);}d.truncate(39999);
    let sr=sha_hex(&d);let mut rows=Vec::new();
    let bo=train_body("T",1,&d[..8000],5,&mut rows,"seat",&sr)?;
    if bo.accepted+bo.held!=400{return Err("selftest cell count".into());}
    // epoch root ordering + domain sep
    let l1=vec!["b".to_string(),"a".to_string()];let l2=vec!["a".to_string(),"b".to_string()];
    if epoch_root(1,"p",&l1)!=epoch_root(1,"p",&l2){return Err("epoch order".into());}
    if epoch_root(1,"p",&l1)==epoch_root(2,"p",&l1){return Err("epoch e".into());}
    let a=leaf(&[("x","y"),("z","")]);let b=leaf(&[("x","yz"),("z","")]);if a==b{return Err("length prefix".into());}
    println!("SELFTEST_PASS|body=400cells_reversible|epoch_root=ordered_domain_separated");
    Ok(())
}

fn flag(a:&[String],n:&str)->R<String>{let i=a.iter().position(|x|x==n).ok_or(format!("missing {}",n))?;a.get(i+1).cloned().ok_or(format!("missing val {}",n))}
fn main()->Result<(),String>{
    let a:Vec<String>=env::args().collect();
    if a.len()<2{return Err("usage: selftest | build --source DIR --output DIR [--seat PID]".into());}
    match a[1].as_str(){
        "selftest"=>selftest(),
        "build"=>{let s=PathBuf::from(flag(&a,"--source")?);let o=PathBuf::from(flag(&a,"--output")?);let seat=flag(&a,"--seat").unwrap_or("8467a937cba309f7".into());run(&s,&o,&seat)},
        _=>Err("unknown".into()),
    }
}
