// Source: data/benchmarks/sv-benchmarks/loop-invariants/linear-inequality-inv-a.c
extern unsigned int unknown_uchar(void);

/*@
  requires !(n == 0);
  requires n <= 255;
*/
void loopy_362(unsigned int n) {
  
  
  unsigned int v = 0;
  unsigned int s = 0;
  unsigned int i = 0;
  while (i < n) {
    v = unknown_uchar();
    s += v;
    ++i;
  }
  if (s < v) {
    {; 
//@ assert(\false);
};
    return;
  }
  if (s > 65025) {
    {; 
//@ assert(\false);
};
    return;
  }
  return;
}