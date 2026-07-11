// Source: data/benchmarks/LinearArbitrary-SeaHorn/invgen/bind_expands_vars2.c
extern int unknown(void);

extern int unknown();

/*@
  requires MAXDATA > 0;
  requires (n1 <= MAXDATA * 2);
  requires (cp1_off <= n1);
  requires (n2 <= MAXDATA*2 - n1);
*/
void loopy_30(int cp1_off, int n1, int n2, int mc_i, int MAXDATA) {

  
  

  

  

  

  {
  mc_i = 0;
  while (mc_i < n2) {
    {;
    //@ assert(cp1_off+mc_i < MAXDATA * 2);
    }
    mc_i++;
  }
}

 END:  return;
}