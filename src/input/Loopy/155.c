// Source: data/benchmarks/accelerating_invariant_generation/cav/39.c
extern int unknown(void);

int __BLAST_NONDET;
int unknown(){
    int x; return x;
}

/*@
  requires MAXPATHLEN > 0;
*/
void loopy_155(int MAXPATHLEN)
{
  
  int buf_off;
  int pattern_off;
  int bound_off;

  int glob3_pathbuf_off;
  int glob3_pathend_off;
  int glob3_pathlim_off;
  int glob3_pattern_off;
  int glob3_dc;

  

  buf_off = 0;
  pattern_off = 0;

  bound_off = 0 + (MAXPATHLEN + 1) - 1;

  glob3_pathbuf_off = buf_off;
  glob3_pathend_off = buf_off;
  glob3_pathlim_off = bound_off;
  glob3_pattern_off = pattern_off;

  glob3_dc = 0;
  {
  while (1) {
    if (glob3_pathend_off + glob3_dc >= glob3_pathlim_off) break;
        else {
          
          glob3_dc++;
          
          if(glob3_dc <= -1 || glob3_dc >= MAXPATHLEN + 1)
          {goto ERROR; { ERROR: {; 
    //@ assert(\false);
    }
    }}
          if (unknown()) goto END;
        }
  }
}
 END:  return;
}