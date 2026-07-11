// Source: data/benchmarks/code2inv/118.c

void loopy_234(int size) {
  
  int i;
  
  int sn;
  
  (sn = 0);
  (i = 1);
  
  while ((i <= size)) {
    {
    (i  = (i + 1));
    (sn  = (sn + 1));
    }

  }
  
if ( (sn != size) )
{;
//@ assert( (sn == 0) );
}

}